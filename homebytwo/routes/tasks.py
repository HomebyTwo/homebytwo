import logging

from celery import group, shared_task
from garmin_uploader.api import GarminAPIException

from .models import (
    Activity,
    ActivityPerformance,
    ActivityType,
    Athlete,
    Route,
    WebhookTransaction,
)

logger = logging.getLogger(__name__)


@shared_task
def import_strava_activities_task(athlete_id):
    """
    import or update all Strava activities for an athlete.
    This task generates one query to the Strava API for every 200 activities.
    """
    # log task request
    logger.info("import Strava activities for {user_id}".format(user_id=athlete_id))

    athlete = Athlete.objects.get(pk=athlete_id)
    activities = Activity.objects.update_user_activities_from_strava(athlete)

    return [activity.strava_id for activity in activities if activity.streams is None]


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
    logger.info("import Strava activity streams for activity {}".format(strava_id))

    try:
        activity = Activity.objects.get(strava_id=strava_id)
    except Activity.DoesNotExist:
        return "Activity {} has been deleted from the Database".format(strava_id)

    imported = activity.save_streams_from_strava()

    if imported:
        return "Streams successfully imported for activity {}".format(strava_id)
    else:
        return "Streams not imported for activity {}".format(strava_id)


@shared_task
def train_prediction_models_task(athlete_id):
    """
    train prediction model for a given activity_performance object
    """
    logger.info(f"Fitting prediction models for athlete: {athlete_id}")

    athlete = Athlete.objects.get(id=athlete_id)
    activities = athlete.activities.filter(
        activity_type__name__in=ActivityType.SUPPORTED_ACTIVITY_TYPES
    )
    activities = activities.order_by("activity_type")
    activities = activities.distinct("activity_type")

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

    # log message
    log_message = "Upload route {route_id} to garmin for user {user_id}"

    # retrieve route
    route = Route.objects.select_related("athlete").get(pk=route_id)

    # retrieve athlete from DB if different from route athlete
    if athlete_id and athlete_id != route.athlete.id:
        # retrieve athlete from DB
        athlete = Athlete.objects.get(pk=athlete_id)
        # log task
        logger.info(log_message.format(route_id=route_id, user_id=athlete.user.id))

    else:
        # defaults to `route.athlete` in `route.upload_to_garmin` method
        athlete = None
        # log task
        logger.info(
            log_message.format(route_id=route_id, user_id=route.athlete.user.id)
        )

    try:
        # upload to Garmin Connect
        garmin_activity_url, uploaded = route.upload_to_garmin(athlete)

    except GarminAPIException as e:
        # remove Garmin ID if status was uploading
        if route.garmin_id == 1:
            route.garmin_id = None
            route.save(update_fields=["garmin_id"])

        return "Garmin API failure: {}".format(e)

    if uploaded:
        return (
            "Route '{route}' successfully uploaded to Garmin connect at {url}".format(
                route=str(route), url=garmin_activity_url
            )
        )


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
                _process_transaction(transaction)
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


def _process_transaction(transaction):
    """
    process transactions created by the Strava Event Webhook
    """

    # find the Strava Athlete
    athlete = Athlete.objects.get(
        user__social_auth__provider="strava",
        user__social_auth__uid=transaction.body["owner_id"],
    )

    # retrieve event values to process
    object_type = transaction.body["object_type"]
    object_id = transaction.body["object_id"]
    aspect_type = transaction.body["aspect_type"]

    # create a new activity if it does not exist already
    if object_type == "activity":

        # retrieve the activity from the database if it exists
        try:
            activity = Activity.objects.get(strava_id=object_id)

        # if the activity does not exist, create a stub
        except Activity.DoesNotExist:
            activity = Activity(athlete=athlete, strava_id=object_id)

        # create or update activity from the Strava server
        if aspect_type in ["create", "update"]:
            activity.update_from_strava()

        # delete activity, if it exists
        if aspect_type == "delete" and activity.id:
            activity.delete()

    else:
        logger.info(f"No action triggered by Strava Event: {object_type}")
