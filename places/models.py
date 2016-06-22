from __future__ import unicode_literals

from django.contrib.gis.db import models

# Create your models here.

class Place(models.Model):
    place_type = models.CharField(max_length=50)
    altitude = models.FloatField()
    name = models.CharField(max_length=250)
    geom = models.MultiPointField(srid=21781)