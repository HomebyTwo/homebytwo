from django.conf import settings
from django.contrib.staticfiles import finders

from django.contrib.gis.db import models
from django.contrib.auth.models import User
from .segment import Segment
from django.contrib.gis.measure import Distance
from django.contrib.gis.geos import Point

import googlemaps


class Track(models.Model):

    class Meta:
        abstract = True

    name = models.CharField(max_length=100)
    description = models.TextField('Textual description', default='')

    # link to user
    user = models.ForeignKey(User, on_delete=models.CASCADE)

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

    # Returns poster picture for the list view
    def get_poster_picture(self):
        if finders.find('routes/images/' + str(self.id) + '.jpg'):
            return 'routes/images/' + str(self.id) + '.jpg'
        else:
            return 'routes/images/default.jpg'

    def get_length(self):
        return Distance(m=self.length)

    def get_totalup(self):
        return Distance(m=self.totalup)

    def get_totaldown(self):
        return Distance(m=self.totaldown)

    def get_start_altitude(self):
        start_altitude = self.get_point_altitude_along_track(0)
        return start_altitude

    def get_end_altitude(self):
        end_altitude = self.get_point_altitude_along_track(1)
        return end_altitude

    def get_point_altitude_along_track(self, location=0):
        point = self.geom.interpolate_normalized(location)

        # format coordoinates for Google Maps API
        point.transform(4326)
        coords = (point.y, point.x)

        # request altitude
        gmaps = googlemaps.Client(key=settings.GOOGLEMAPS_API_KEY)
        result = gmaps.elevation(coords)
        altitude = result[0]['elevation']

        # return distance object
        return Distance(m=altitude)

    def segment_route_with_points(self, places):
        """
        Creates segments from a list of places.

        The list of places should be annotated with their location
        along the line: line_location a float between 0 and 1.
        """
        # SQL to create a subline along a route using ST_Line_Substring
        sql = ('SELECT id, ST_Line_Substring(routes_route.geom, %s, %s) as geom'
               'FROM routes_route WHERE routes_route.id = %s')

        # Calculate distance between route start and first place
        first_place = places[0]
        starting_point = Point(self.geom[0])
        distance_to_first_place = starting_point.distance(first_place.geom)

        # Create a private first segment if start
        # is more than 50m away from first place.
        if distance_to_first_place > 50:
            rawquery = self.objects.raw(sql, [0, first_place.line_location,
                                              self.id])

            # First result returns the geometry
            geom = rawquery[0].geom
            name = 'start of %s to %s' % [self.name, first_place.name]
            args = {
                'name': name,
                'start_place': None,
                'end_place': first_place,
                'geom': geom,
                'elevation_up': 0,
                'elevation_down': 0,
                'private': True
            }

            segment = Segment.objects.create(args)
            segment.get_elevation_data()

        # Save segments
        for i, place in enumerate(places[:-1]):
            # Raw query to create the segment geom
            rawquery = self.objects.raw(sql, [place.line_location,
                                              places[i+1].line_location,
                                              self.id])

            # First result returns the geometry
            geom = rawquery[0].geom

            # By default, the name of the segment is 'Start Place - End Place'
            name = place.name + ' - ' + places[i+1].name
            args = {
                    'name': name,
                    'start_place': place,
                    'end_place': places[i+1],
                    'geom': geom,
                    'elevation_up': 0,
                    'elevation_down': 0,
                    'private': False,
            }

            segment = Segment.objects.create(args)
            segment.get_elevation_data()

    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.name
