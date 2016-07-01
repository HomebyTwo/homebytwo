from __future__ import unicode_literals

from django.conf import settings
from django.contrib.staticfiles import finders

from django.contrib.gis.db import models
from django.contrib.gis.measure import Distance

import googlemaps


class Place(models.Model):
    type = models.CharField(max_length=50)
    altitude = models.FloatField()
    name = models.CharField(max_length=250)
    description = models.TextField('Text description of the Place', default='')
    updated = models.DateTimeField('Time of last update', auto_now=True)
    created = models.DateTimeField('Time of last creation', auto_now_add=True)
    lang = models.CharField(max_length=50)

    geom = models.PointField(srid=21781)

    # Returns altitude for a place and updates the database entry
    def get_gmaps_elevation(self):
        # Extract first geometry from Multipoint
        geom = self.geom

        # Transform coords to Gmaps SRID
        geom.transform(4326)

        # Query gmaps API for altitude
        gmaps = googlemaps.Client(key=settings.GOOGLEMAPS_API_KEY)
        coords = (geom.coords.y, geom.coords.x)
        result = gmaps.elevation(coords)

        # Update altitude information for point
        self.altitude = result[0]['elevation']
        self.save()

        return self.altitude
