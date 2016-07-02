from __future__ import unicode_literals

from django.contrib.gis.db import models
from .place import Place


class Segment(models.Model):
    name = models.CharField(max_length=100, default='')

    # Start place of the segment
    start_place = models.ForeignKey(
            Place,
            on_delete=models.PROTECT,
            related_name='starts',
            null=True
        )

    # End place of the segment
    end_place = models.ForeignKey(
            Place,
            on_delete=models.PROTECT,
            related_name='ends',
            null=True
        )

    # Linestring
    geom = models.LineStringField('line geometry', srid=21781)

    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.name
