import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured

import codaio.err
from celery import group, shared_task
from celery.schedules import crontab
from codaio import Cell, Coda, Document
from garmin_uploader.api import GarminAPIException
from requests.exceptions import ConnectionError
from stravalib.exc import Fault, RateLimitExceeded

from ..celery import app as celery_app
from ..importers.elevation_api import get_elevations_from_geom
from .models import (Activity, ActivityPerformance, ActivityType, Athlete, Route,
                     WebhookTransaction)
from .models.activity import is_activity_supported, update_user_activities_from_strava

logger = logging.getLogger(__name__)


@shared_task
def import_strava_activities_task(athlete_id):
    """
    import or update all Strava activities for an athlete.
    This task generates one query to the Strava API for every 200 activities.
    """
    logger.info(f"import Strava activities for athlete with id: {athlete_id}.")
    athlete = Athlete.objects.get(pk=athlete_id)

    try:
        activities = update_user_activities_from_strava(athlete)
    except (Fault, RateLimitExceeded) as error:
        message = "Activities for athlete_id: `{}` could not be retrieved from Strava."
        message.format(athlete_id)
        message += f"Error was: {error}. "
        logger.error(message, exc_info=True)
        return []

    # upon successful import, set the athlete's flag to True
    athlete.activities_imported = True
    athlete.save(update_fields=["activities_imported"])

    # return the list of activities for importing the streams
    return [
        activity.strava_id
        for activity in activities
        if activity.streams is None and not activity.skip_streams_import
    ]


@shared_task
def import_strava_activities_streams_task(activity_ids):
    return group(
        import_strava_activity_streams_task(activity_id) for activity_id in activity_ids
    )


@shared_task(rate_limit="40/m")
def import_strava_activity_streams_task(strava_id):
    """
    fetch time, altitude, distance and moving streams for an activity from the Strava API-
    This task generates one API call for every activity.
    """
    # log task request
    logger.info("import Strava activity streams for activity {}.".format(strava_id))

    # get the activity from the database
    try:
        activity = Activity.objects.get(strava_id=strava_id)
    except Activity.DoesNotExist:
        return "Activity {} has been deleted from the Database. ".format(strava_id)

    # marked as skip because of missing stream data
    if activity.skip_streams_import:
        return "Skipped importing streams for activity {}. ".format(strava_id)

    # get streams from Strava
    try:
        imported = activity.update_activity_streams_from_strava()
    except (ConnectionError, Fault) as error:
        message = (
            f"Streams for activity {strava_id} could not be retrieved from Strava."
        )
        message += f"error was: {error}. "
        logger.error(message)
        return message

    if imported:
        return "Streams successfully imported for activity {}.".format(strava_id)
    else:
        return "Streams not imported for activity {}.".format(strava_id)


@shared_task
def train_prediction_models_task(athlete_id):
    """
    train prediction model for a given activity_performance object
    """
    logger.info(f"Fitting prediction models for athlete: {athlete_id}. ")

    athlete = Athlete.objects.get(id=athlete_id)
    activities = athlete.activities.filter(
        activity_type__name__in=ActivityType.SUPPORTED_ACTIVITY_TYPES
    )
    activities = activities.order_by("activity_type")
    activities = activities.distinct("activity_type")

    if not activities:
        return f"No prediction model trained for athlete: {athlete}"

    message = f"Prediction models trained for athlete: {athlete}."
    for activity in activities:
        activity_performance, created = ActivityPerformance.objects.get_or_create(
            athlete=athlete, activity_type=activity.activity_type
        )
        message += activity_performance.train_prediction_model()

    return message


@shared_task
def upload_route_to_garmin_task(route_id, athlete_id=None):
    """
    uploads a route schedule as activity to the Homebytwo account on
    Garmin Connect.

    This allows athletes to use the race against activity feature on
    compatible Garmin devices.
    """

    # retrieve route and athlete
    route = Route.objects.get(pk=route_id)
    athlete = Athlete.objects.get(pk=athlete_id) if athlete_id else route.athlete

    # log message
    logger.info(f"Upload route {route.id} to garmin for user {athlete.user.id}")

    try:
        # upload to Garmin Connect
        garmin_activity_url, uploaded = route.upload_to_garmin(athlete)

    except GarminAPIException as error:
        # remove Garmin ID if status was uploading
        if route.garmin_id == 1:
            route.garmin_id = None
            route.save(update_fields=["garmin_id"])

        return "Garmin API failure: {}".format(error)

    if uploaded:
        message = "Route '{}' successfully uploaded to Garmin connect at {}."
        return message.format(route, garmin_activity_url)


@shared_task
def update_route_elevation_data_task(route_id, provider="elevation_api"):
    """
    update route altitude data from elevation API
    """
    logger.info(f"retrieving elevation data for route with id: {route_id}.")
    route = Route.objects.get(pk=route_id)
    elevations = get_elevations_from_geom(route.geom, provider)

    if elevations:
        route.data.altitude = elevations
        route.save(update_fields=["data"])
        return f"Elevation updated for route: {route}."
    else:
        return f"Error while retrieving elevation data for route with id: {route_id}."


@shared_task
def process_strava_events():
    """
    process events received from Strava and saved as transactions in the database

    Note that, in order to save calls to the Strava API, only the most recent event
    is processed for each object.

    """

    # run_every = crontab(minute="*/15")  # this will run every 15 minutes
    # retrieve only latest unprocessed transaction per object
    unprocessed_transactions = WebhookTransaction.objects.filter(
        status=WebhookTransaction.UNPROCESSED
    )
    distinct_transactions = unprocessed_transactions.distinct(
        "body__object_id", "body__object_type"
    )
    distinct_transactions = distinct_transactions.order_by(
        "body__object_id", "body__object_type", "-date_generated"
    )

    # handle errors and status
    for transaction in unprocessed_transactions:
        if transaction in distinct_transactions:
            try:
                process_transaction(transaction)
                transaction.status = WebhookTransaction.PROCESSED
                transaction.save()

            except Athlete.DoesNotExist:
                transaction.status = WebhookTransaction.ERROR
                logger.exception("Athlete not found for this Strava event.")
                transaction.save()

            except Exception as error:
                transaction.status = WebhookTransaction.ERROR
                logger.exception(f"Error processing Strava event: {error}")
                transaction.save()

        # mark duplicate entries for the same object as SKIPPED
        else:
            logger.info("webhook transaction {} skipped".format(transaction.id))
            transaction.status = WebhookTransaction.SKIPPED
            transaction.save()


def process_transaction(transaction):
    """
    process transactions created by the Strava Event Webhook
    """

    # find the Strava Athlete in the database
    athlete = Athlete.objects.get(
        user__social_auth__provider="strava",
        user__social_auth__uid=transaction.body["owner_id"],
    )

    # event values to process
    object_type = transaction.body["object_type"]
    object_id = transaction.body["object_id"]
    aspect_type = transaction.body["aspect_type"]

    # we only support activity update
    if not object_type == "activity":
        logger.info(
            f"Strava event with object type: {object_type} has triggered no action. "
        )
        return

    # get activity from database or create a new one
    activity = Activity.get_or_stub(object_id, athlete)

    # create or update activity with Strava
    if aspect_type in ["create", "update"]:
        # retrieve activity information from Strava
        strava_activity = activity.get_activity_from_strava()
        # activity was found on Strava and is supported by Homebytwo
        if strava_activity and is_activity_supported(strava_activity):
            activity.update_with_strava_data(strava_activity)
            return True

    # Activity is not supported by Homebytwo or the transaction `aspect_type` is `delete`
    if activity.id:
        activity.delete()
        logger.info(f"Strava activity: {object_id} was deleted from Homebytwo.")


@celery_app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    # everyday at noon
    sender.add_periodic_task(
        crontab(hour=12, minute=0),
        report_usage_to_coda.si(),
    )


@celery_app.task
def report_usage_to_coda():
    """
    report key performance metrics to coda.io

    runs only if `CODA_API_KEY` is set. It should only be configured in production
    to prevent reporting data from local or staging environments.
    """
    if not settings.CODA_API_KEY:
        return "CODA_API_KEY is not set."

    coda = Coda(settings.CODA_API_KEY)
    doc_id, table_id = settings.CODA_DOC_ID, settings.CODA_TABLE_ID
    doc = Document(doc_id, coda=coda)
    table = doc.get_table(table_id)

    rows = []
    for user in User.objects.exclude(athlete=None):
        mapping = {
            "ID": user.id,
            "Username": user.username,
            "Email": user.email,
            "Date Joined": user.date_joined.__str__(),
            "Last Login": user.last_login.__str__(),
            "Routes Count": user.athlete.tracks.count(),
            "Strava Activities Count": user.athlete.activities.count(),
        }
        try:
            rows.append(
                [
                    Cell(column=table.get_column_by_name(key), value_storage=value)
                    for key, value in mapping.items()
                ]
            )
        except codaio.err.ColumnNotFound as error:
            message = f"Missing column in coda document at https://coda.io/d/{doc_id}: {error}"
            logger.error(message)
            raise ImproperlyConfigured(message)

    table.upsert_rows(rows, key_columns=["ID"])

    return f"Updated {len(rows)} rows in Coda table at https://coda.io/d/{doc_id}"
