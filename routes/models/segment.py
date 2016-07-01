from __future__ import unicode_literals

from django.conf import settings

from django.contrib.gis.db import models
from .place import Place


class Segment(models.Model):
    # Start place of the segment
    start_place = models.ForeignKey(
            Place,
            on_delete=models.PROTECT,
            related_name='starts',
        )

    # End place of the segment
    end_place = models.ForeignKey(
            Place,
            on_delete=models.PROTECT,
            related_name='ends',
        )

    # Linestring
    geom = models.LineStringField('line geometry', srid=21781)
