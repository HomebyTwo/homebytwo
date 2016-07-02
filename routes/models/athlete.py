from django.contrib.gis.db import models
from django.contrib.auth.models import User
from .activity import ActivityType


class Athlete(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    strava_token = models.CharField(max_length=100)
    switzerland_mobility_cookie = models.CharField(max_length=100)

    # activities that the athlete practices with typical performance
    activies = models.ManyToManyField(ActivityType, through='ActivityPerformance')


class ActivityPerformance(models.Model):
    # Intermediate model for athlete - activity type
    athlete = models.ForeignKey(Athlete, on_delete=models.CASCADE)
    activity_type = models.ForeignKey(ActivityType, on_delete=models.CASCADE)

    # Vertical speed up used for time calculation in meters/hour
    vam_up = models.FloatField(default=400)
    # Vertical speed down used for time calculation in meters/hour
    vam_down = models.FloatField(default=2000)
    # Horizontal speed used for time calculation in meters/hour
    flat_pace = models.FloatField(default=4000)
