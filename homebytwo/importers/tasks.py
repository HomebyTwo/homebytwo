from .models import (
    Activity,
    Athlete,
)
from celery import shared_task


@shared_task
def import_strava_activities(athlete_id):
    athlete = Athlete.objects.get(pk=athlete_id)
    activities = Activity.objects.update_user_activities_from_strava(athlete)
    return activities.count()
