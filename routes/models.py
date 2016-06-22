from __future__ import unicode_literals

from django.contrib.gis.db import models

# Create your models here.
class Route(models.Model):
    name = models.CharField(max_length=50)
    swissmobility_id = models.BigIntegerField(unique=True)
    totalup = models.FloatField('Total elevation difference up in m', default=0)
    totaldown = models.FloatField('Total elevation difference down in mq', default=0)
    length = models.FloatField('Total length of the track in m', default=0)
    description = models.TextField('Text description of the Route')

    # GeoDjango-specific field type: LineString
    geom = models.LineStringField('line geometry', srid=21781)

    # Returns the string representation of the model.
    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.name