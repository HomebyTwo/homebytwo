from __future__ import unicode_literals

from django.conf import settings
from django.contrib.staticfiles import finders

from django.contrib.gis.db import models
from django.contrib.gis.measure import Distance

import googlemaps


class Route(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField('Text description of the Route', default='')

    # elevation gain in m
    totalup = models.FloatField('Total elevation gain in m', default=0)
    # elevation loss in m
    totaldown = models.FloatField('Total elevation loss in m', default=0)
    # route distance in m
    length = models.FloatField('Total length of the track in m', default=0)

    # creation and update date
    updated = models.DateTimeField('Time of last update', auto_now=True)
    created = models.DateTimeField('Time of creation', auto_now_add=True)

    # geographic information
    geom = models.LineStringField('line geometry', srid=21781)

    # Returns the string representation of the model.
    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.name

    # Returns poster picture for the list view
    def get_poster_picture(self):
        if finders.find('routes/images/' + str(self.id) + '.jpg'):
            return 'routes/images/' + str(self.id) + '.jpg'
        else:
            return 'routes/images/default.jpg'

    def get_distance(self):
        return Distance(m=self.length)

    def get_point_elevation(self, location=0):
        point = self.geom.interpolate_normalized(location)
        point.transform(4326)
        coords = (point.y, point.x)

        gmaps = googlemaps.Client(key=settings.GOOGLEMAPS_API_KEY)
        result = gmaps.elevation(coords)

        return result[0]['elevation']


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


class Segment(models.Model):
    start_place = models.ForeignKey(Place, on_delete=models.PROTECT,
                                    related_name='starts')
    end_place = models.ForeignKey(Place, on_delete=models.PROTECT,
                                  related_name='ends')
    geom = models.LineStringField('line geometry', srid=21781)
