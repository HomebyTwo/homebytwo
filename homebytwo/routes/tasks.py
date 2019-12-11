import logging

from django.template.defaultfilters import pluralize

from celery import shared_task
from celery.schedules import crontab
from celery.task import PeriodicTask
from garmin_uploader.api import GarminAPIException

from .models import Activity, Athlete, Route, WebhookTransaction

logger = logging.getLogger(__name__)


@shared_task
def import_strava_activities_task(athlete_id):
    """
    import or update all Strava activities for an athlete.

    This task generates one query to the Strava API for 200 activities.
    """
    athlete = Athlete.objects.get(pk=athlete_id)
    activities = Activity.objects.update_user_activities_from_strava(athlete)
    return "The athlete now has {0} activit{1} saved in the database.".format(
        len(activities), pluralize(len(activities), "y,ies")
    )


@shared_task
def upload_route_to_garmin_task(route_id, athlete_id=None):
    """
    uploads a route schedule as activity to the Homebytwo account on
    Garmin Connect.

    This allows athletes to use the race against activity feature on
    compatible Garmin devices.
    """

    # retrieve route
    route = Route.objects.select_related("athlete").get(pk=route_id)

    # retrieve athlete from DB if different from route athlete
    if athlete_id and athlete_id != route.athlete.id:
        athlete = Athlete.objects.get(pk=athlete_id)
    else:
        athlete = None

    # upload to Garmin Connect
    try:
        garmin_activity_url, uploaded = route.upload_to_garmin(athlete)
    except GarminAPIException as e:
        # remove Garmin ID if status was uploading
        if route.garmin_id == 1:
            route.garmin_id = None
            route.save(update_fields=["garmin_id"])

        return 'Garmin API failure: {}'.format(e)

    if uploaded:
        return "Route '{route}' successfully updated to Garmin connect at {url}".format(
            route=str(route), url=garmin_activity_url
        )


class ProcessStravaEvents(PeriodicTask):
    """
    process events received from Strava and saved as transactions in the database

    Note that, in order to save calls to the Strava API, only the most recent event
    is processed for each object.

    """

    run_every = crontab(minute="*/15")  # this will run every 15 minutes

    def run(self):
        unprocessed_transactions = self.get_transactions_to_process()

        # process only one transaction per object
        distinct_transactions = unprocessed_transactions.distinct(
            "body__object_id", "body__object_type"
        )

        # sort by `-date_generated` to keep the latest
        distinct_transactions = distinct_transactions.order_by(
            "body__object_id", "body__object_type", "-date_generated"
        )

        for transaction in unprocessed_transactions:

            # only process the latest event for each object
            if transaction in distinct_transactions:
                try:
                    self.process_transaction(transaction)
                    transaction.status = WebhookTransaction.PROCESSED
                    transaction.save()

                except Exception:
                    transaction.status = WebhookTransaction.ERROR
                    logger.exception("Error handling the Strava event.")

                    transaction.save()

            # mark duplicate entries for an object as SKIPPED
            else:
                transaction.status = WebhookTransaction.SKIPPED
                transaction.save()

    def get_transactions_to_process(self):
        return WebhookTransaction.objects.filter(status=WebhookTransaction.UNPROCESSED)

    def process_transaction(self, transaction):

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
