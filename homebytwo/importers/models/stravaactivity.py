from django.contrib.auth.models import User
from django.contrib.gis.db import models


class StravaActivityManager(models.Manager):
    """
    Manager for athlete activities retrieved from Strava
    """
    def get_activities_from_server(strava_token):
        """
        Retrieve activities from Strava with the following args:
        - `after` start date is after specified value (UTC)_ datetime.datetime or str or None
        - `before` start date is before specified value (UTC): datetime.datetime or str or None
        - `limit` Maximum activites retrieved

        Activities are saved in the Database
        """
        return strava_token


class StravaActivity(models.Model):
    """
    Athlete activities retrieved from Strava
    """
    name = models.CharField(max_length=256)

    # link to user
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # register the custom manager
    objects = StravaActivityManager()
