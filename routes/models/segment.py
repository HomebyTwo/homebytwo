from __future__ import unicode_literals

from django.contrib.gis.db import models
from .place import Place


class Segment(models.Model):
    name = models.CharField(max_length=100, default='')
    elevation_up = models.FloatField('elevation gain in m', default=0)
    elevation_down = models.FloatField('elevation loss in m', default=0)

    # Start place of the segment
    start_place = models.ForeignKey(Place, on_delete=models.PROTECT,
                                    related_name='starts', null=True)

    # End place of the segment
    end_place = models.ForeignKey(Place, on_delete=models.PROTECT,
                                  related_name='ends', null=True)

    # Linestring
    geom = models.LineStringField('line geometry', srid=21781)

    def get_elevation_data(self):
        """
        Returns a tuple with (elevation_up, elevation_down)
        """
        return (0, 0)

    def calculate_duration(self):
        pass

    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.name
