from django.contrib.gis.db import models
from django.contrib.auth.models import User


class Athlete(models.Model):
    # Extend default user model
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # Save remote authentications
    strava_token = models.CharField(max_length=100, null=True)

    # activities that the athlete practices with personal performance
    activies = models.ManyToManyField(
                'ActivityType',
                through='ActivityPerformance'
            )


"""
A snippet to create a user profile the first time it is accessed.
https://www.djangorocks.com/snippets/automatically-create-a-django-profile.html
"""
User.athlete = property(lambda u: Athlete.objects.get_or_create(user=u)[0])
