from django.contrib.auth.models import User
from django.contrib.gis.db import models


class Athlete(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    strava_token = models.CharField(max_length=100)
    switzerland_mobility_cookie = models.CharField(max_length=100)
