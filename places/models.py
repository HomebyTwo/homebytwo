from __future__ import unicode_literals

from django.contrib.gis.db import models

# Create your models here.

class Place(models.Model):
    place_type = models.CharField(max_length=50)
    altitude = models.FloatField()
    name = models.CharField(max_length=250)
    geom = models.MultiPointField(srid=21781)
    description = models.TextField('Text description of the Place', default='')
    updated = models.DateTimeField('Time of last update', auto_now=True)
    created = models.DateTimeField('Time of last creation', auto_now_add=True)
