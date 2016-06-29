from __future__ import unicode_literals

from django.conf import settings

from django.contrib.gis.db import models
from django.contrib.gis.measure import Distance
from django.contrib.staticfiles import finders
from autoslug import AutoSlugField

import googlemaps


class SwitzerlandMobilityRoute(models.Model):
    name = models.CharField(max_length=50)
    totalup = models.FloatField('Total elevation difference up in m', default=0)
    totaldown = models.FloatField('Total elevation difference down in m', default=0)
    length = models.FloatField('Total length of the track in m', default=0)
    description = models.TextField('Text description of the Route', default='')
    updated = models.DateTimeField('Time of last update', auto_now=True)
    created = models.DateTimeField('Time of last creation', auto_now_add=True)
    geom = models.LineStringField('line geometry', srid=21781)
    switzerland_mobility_id = models.BigIntegerField(unique=True)

    # Returns poster picture for the list view
    def get_poster_picture(self):
        if finders.find('routes/images/' + str(self.swissmobility_id) + '.jpg'):
            return 'routes/images/' + str(self.switzerland_mobility_id) + '.jpg'
        else:
            return 'routes/images/default.jpg'

    def get_distance(self, unit='m'):
        return Distance(**{unit: self.length})

    def get_point_elevation_on_line(self, location=0):
        sql = (
                'SELECT ST_Line_Interpolate_Point(%s, %s) '
                'FROM routes_place '
                'WHERE id = %s'
            )

        point = Route.objects.raw(sql,(self.geom, location, self.id))

        point.geom.transform(4326)

        gmaps = googlemaps.Client(key=settings.GOOGLEMAPS_API_KEY)
        result = gmaps.elevation(point.geom.coords)

        return result[0]['elevation']
