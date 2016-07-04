from django.contrib.gis.db import models
from django.contrib.auth.models import User


class Athlete(models.Model):
    # Extend default user model
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # Save remote authentications
    strava_token = models.CharField(max_length=100, null=True)
    switzerland_mobility_cookie = models.CharField(max_length=100, null=True)

    # activities that the athlete practices with personal performance
    activies = models.ManyToManyField(
                'ActivityType',
                through='ActivityPerformance'
            )
