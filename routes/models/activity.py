from django.contrib.gis.db import models


class ActivityType(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
