from __future__ import unicode_literals

from django.contrib.gis.db import models

# Create your models here.
class Track(models.Model):
    name = models.CharField(max_length=50)
    swissmobility_id = models.BigIntegerField(unique=True)
    totalup = models.FloatField('Total elevation difference up', default=0)
    totaldown = models.FloatField('Total elevation difference down', default=0)
    length = models.FloatField('Total length of the track in m', default=0)

    # GeoDjango-specific field type: LineString
    geom = models.LineStringField('line geometry', srid=21781)

    # Returns the string representation of the model.
    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.name

class SwissPlace(models.Model):
    uuid = models.CharField(max_length=38)
    place_type = models.CharField(max_length=50)
    altitude = models.FloatField()
    name_uuid = models.CharField(max_length=38)
    name = models.CharField(max_length=250)
    lang_code = models.CharField(max_length=50)
    name_type = models.CharField(max_length=20)
    name_group = models.CharField(max_length=38)
    geom = models.MultiPointField(srid=21781)