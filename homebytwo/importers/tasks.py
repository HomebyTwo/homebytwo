from celery import shared_task

from .models import StravaActivity


@shared_task
def import_strava_activities(user_id, strava_token):
    activities = StravaActivity.objects.get_activities_from_server(
        self, strava_token=strava_token,
    )
    return activities
