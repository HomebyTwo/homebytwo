from __future__ import unicode_literals

from django.contrib.gis.db import models
from .track import Track


class Route(Track):

    # source and unique id at the source that the route was imported from
    source_id = models.BigIntegerField()
    data_source = models.CharField('Where the route came from',
                                   default='homebytwo', max_length=50)

    # Each route is made of segments
    # segments = models.ManyToManyField(Segment)

    class Meta:
        unique_together = ('user', 'data_source', 'source_id')
