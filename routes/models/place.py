from __future__ import unicode_literals

from django.contrib.gis.db import models
from django.conf import settings
from django.contrib.gis.measure import D
from django.contrib.gis.db.models.functions import Distance, GeoFunc, GeomValue
from django.utils import six
import googlemaps
import requests
import json
from datetime import datetime


class LineLocatePoint(GeoFunc):
    """
    implements ST_LineLocatePoint that is still missing in GeoDjango
    for some reason: https://code.djangoproject.com/ticket/12410.

    This could be improved as I had no idea of how to tell GeoFunc
    that the first arg was the one the treat as a geom,
    unlike in GeoFuncWithGeoParam(GeoFunc).

    At least, I learned something about list comprehensions.
    """
    def __init__(self, *expressions, **extra):
        expressions = [
            arg if isinstance(arg, six.string_types) else GeomValue(arg)
            for arg in expressions
        ]
        super(LineLocatePoint, self).__init__(*expressions, **extra)

    output_field_class = models.FloatField
    arity = 2


class PlaceManager(models.Manager):
    """
    Manager to retrieve places.
    """
    def get_public_transport(self):
        self.filter(public_transport=True)

    def get_places_from_line(self, line, max_distance=50):
        """
        returns places with a max_distance of a Linestring Geometry within
        ordered by and annotated with location along the line
        and distance from the line.
        """

        # convert max_distance to Distance object
        max_d = D(m=max_distance)

        # find all places within max distance from line
        places = Place.objects.filter(geom__dwithin=(line, max_d))

        # annotate with distance to line
        places = places.annotate(distance_from_line=Distance('geom', line))

        # annotate with location along the line between 0 and 1
        places = places.annotate(line_location=LineLocatePoint(line, 'geom'))

        # order by location along the line and distance to the line
        places = places.order_by('line_location', 'distance_from_line')

        return places

    def get_places_within(self, point, max_distance=100):
        # make range a distance object
        max_d = D(m=max_distance)

        # get places within range
        places = self.filter(geom__distance_lte=(point, max_d))

        # annotate with distance
        places = places.annotate(distance_from_line=Distance('geom', point))

        # sort by distance
        places = places.order_by('distance_from_line',)

        return places


class Place(models.Model):
    """
    Places are geographic points.
    They have a name, description and geom
    Places are used to create segments from routes and
    and for public transport connection.
    """

    PLACE_TYPE_CHOICES = (
        ('PLA', 'Place'),
        ('Constructions', (
                ('BDG', 'Single Building'),
                ('OBG', 'Open Building'),
                ('TWR', 'Tower'),
                ('SBG', 'Sacred Building'),
                ('CPL', 'Chapel'),
                ('SHR', 'Wayside Shrine'),
                ('MNT', 'Monument'),
                ('FTN', 'Fountain'),
            )
         ),
        ('Features', (
                ('SUM', 'Summit'),
                ('HIL', 'Hill'),
                ('PAS', 'Pass'),
                ('BEL', 'Belay'),
                ('WTF', 'Waterfall'),
                ('CAV', 'Cave'),
                ('SRC', 'Source'),
                ('BLD', 'Boulder'),
                ('POV', 'Point of View')
            )
         ),
        ('Public Transport', (
                ('BUS', 'Bus Station'),
                ('TRA', 'Train Station'),
                ('OTH', 'Other Station'),
                ('BOA', 'Boat Station'),
            )
         ),
        ('Roads', (
                ('EXT', 'Exit'),
                ('EAE', 'Entry and Exit'),
                ('RPS', 'Road Pass'),
                ('ICG', 'Interchange'),
                ('LST', 'Loading Station'),
            )
         ),
        ('Customs', (
                ('C24', 'Customhouse 24h'),
                ('C24LT', 'Customhouse 24h limited'),
                ('CLT', 'Customhouse limited'),
                ('LMK', 'Landmark'),
            )
         ),
    )

    place_type = models.CharField(max_length=26, choices=PLACE_TYPE_CHOICES)
    name = models.CharField('Name of the place', max_length=250)
    description = models.TextField('Text description of the Place', default='')
    altitude = models.FloatField(null=True)
    public_transport = models.BooleanField(default=False)
    data_source = models.CharField('Where the place came from',
                                   default='homebytwo', max_length=50)
    source_id = models.CharField('Place ID at the data source', max_length=50)

    created_at = models.DateTimeField('Time of creation', auto_now_add=True)
    updated_at = models.DateTimeField('Time of last update', auto_now=True)

    geom = models.PointField(srid=21781)

    objects = PlaceManager()

    class Meta:
        # The pair 'data_source' and 'source_id' should be unique together.
        unique_together = ('data_source', 'source_id',)

    def get_altitude(self):
        return D(m=self.altitude)

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

    def get_public_transport_connections(self,
                                         destination,
                                         via=[],
                                         travel_to_place=False,
                                         travel_datetime=datetime.now(),
                                         is_arrival_time=False,
                                         limit=1,
                                         bike=0):
        """
        Get connection information from the place to a destination
        using the public transport API.
        If travelling to the place instead of from the place,
        the connection can be queried using the travel_to_place=True flag
        An object is returned containing departure and arrival time
        """

        # Ensure the place is a public transport stop
        if not self.public_transport:
            print('Error: place is not connected to public transport network')
            return

        # Base public transport API URL
        url = '%s/connections' % settings.SWISS_PUBLIC_TRANSPORT_API_URL

        # Set origin and destination according to travel_to_place flag
        if travel_to_place:
            origin = destination
            destination = self.name
        else:
            origin = self.name

        # Define API call parameters
        args = {
            'from': origin,
            'to': destination,
            'date': str(travel_datetime.date()),
            'time': travel_datetime.strftime('%H:%S'),
            'isArrivalTime': is_arrival_time,
            'limit': limit,
            'bike': bike,
            'fields[]': [
                         'connections/from/departure',
                         'connections/to/arrival',
                         'connections/duration',
                         'connections/products',
                         ]
        }
        kwargs = {'params': args}

        # Call the API
        try:
            response = requests.get(url, **kwargs)
        except requests.exceptions.ConnectionError:
            print('Error: Could not reach network.')

        if not response.ok:
            print('Server Error: HTTP %s' %
                  (response.status_code, ))
            return

        try:
            data = json.loads(response.text)
        except ValueError:
            print('Error: Invalid API response (invalid JSON)')
            return

        if not data['connections']:
            msg = 'No connections found from "%s" to "%s".' % \
                  (data['from']['name'], data['to']['name'])
            print(msg)

        return data

    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        """
        Source_id references the id at the data source.
        The pair 'data_source' and 'source_id' should be unique together.
        Places created in Homebytwo directly should thus have a source_id
        set.
        In other cases, e.g. importers.Swissname3dPlaces,
        the source_id will be set by the importer model.

        """
        super(Place, self).save(*args, **kwargs)

        # in case of manual homebytwo entries, the source_id will be empty.
        if self.source_id == '':
            self.source_id = str(self.id)
            self.save()


class RoutePlace(models.Model):
    # Intermediate model for route - place
    route = models.ForeignKey('Route', on_delete=models.CASCADE)
    place = models.ForeignKey('Place', on_delete=models.CASCADE)

    # location on the route normalized 0=start 1=end
    line_location = models.FloatField(default=0)

    # Altitude at the route's closest point to the place
    altitude_on_route = models.FloatField()

    def get_altitude_on_route(self, save=True):
        track = self.route
        altitude = track.get_point_altitude_along_track(self.line_location)
        self.altitude_on_route = altitude.m

        return altitude

    def __str__(self):
        return self.place.name

    def __unicode__(self):
        return self.place.name
