import json
from datetime import datetime
from itertools import chain, islice, tee

import googlemaps
import requests
from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.gis.db.models.functions import Distance, LineLocatePoint
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.measure import D
from django.core.exceptions import ValidationError
from django.db import connection


def current_and_next(some_iterable):
    """
    using itertools to make current and next item of an iterable available:
    http://stackoverflow.com/questions/1011938/python-previous-and-next-values-inside-a-loop
    """
    items, nexts = tee(some_iterable, 2)
    nexts = chain(islice(nexts, 1, None), [None])
    return zip(items, nexts)


def LineSubstring(line, start_location, end_location):
    """
    implements ST_Line_Substring
    """
    sql = ("SELECT ST_AsText(ST_Line_SubString("
           "ST_GeomFromText(%(line)s, %(srid)s), %(start)s, %(end)s));")

    with connection.cursor() as cursor:
        cursor.execute(sql, {'line': line.wkt,
                             'srid': line.srid,
                             'start': start_location,
                             'end': end_location})
        geom = cursor.fetchone()[0]

    return GEOSGeometry(geom)


class PlaceManager(models.Manager):
    """
    Manager to retrieve places.
    """
    def get_public_transport(self):
        self.filter(public_transport=True)

    def find_places_along_line(self, line, max_distance=50):
        """
        The `recursive` option addresses the issue of a linestring passing
        near the same place more than once. The normal query uses
        LineLocatePoint and thus can only find each place once.

        The recursive strategy creates a new line substrings between
        the found places and runs the query on these line substrings again.

        If a new place is found on the line substring. We look for other places
        again on the newly created segements. if no new place is found,
        the segment is discarded from the recursion.

        For example, if the geometry passes through these places:

            Start---A---B---A---End

        1/  the first time around, we find these places:

            Start---A---B-------End

        2/  we check for further places along each subsegment:
            a) Start---A
            b) A---B
            c) B---End

        3/  find no additional places in a) and b) but find the place A in c)

            B---A---End

        4/  we check for further places in each subsegment
            and find no additional place.

        """
        places = []
        segments = []

        # initial request to find each visited place once
        places.extend(self.get_places_from_line(line, max_distance))

        if not places:
            return []

        # create segments between the found places
        segments.extend(self.create_segments_from_places(places))

        for segment in segments:

            # find additional places along the segment
            new_places = self.find_places_in_segment(segment, line,
                                                     max_distance)

            if new_places:
                start, end = segment
                places.extend(new_places)
                segments.extend(
                    self.create_segments_from_places(new_places, start, end)
                )

        places.sort(key=lambda o: o.line_location)

        return places

    def get_places_from_line(self, line, max_distance):
        """
        returns places within a max_distance of a Linestring Geometry
        ordered by, and annotated with the `line_location` and the
        `distance_from_line`:

          * `line_location` is the location on the line expressed as a
            float between 0.0 and 1.0.
          * `distance_from_line` is a geodjango Distance object.

        """

        # convert max_distance to Distance object
        max_d = D(m=max_distance)

        # find all places within max distance from line
        places = Place.objects.filter(geom__dwithin=(line, max_d))

        # annotate with distance to line
        places = places.annotate(distance_from_line=Distance('geom', line))

        # annotate with location along the line between 0 and 1
        places = places.annotate(line_location=LineLocatePoint(line, 'geom'))

        # remove start and end places within 1% of start and end location
        places = places.filter(line_location__gt=0.01, line_location__lt=0.99)

        places = places.order_by('line_location')

        return places

    def create_segments_from_places(self, places, start=0, end=1):
        """
        returns a list of segments as tuples with start and end locations
        along the original line.

        """

        # sorted list of line_locations from the list of places as
        # well as the start and the end location of the segment where
        # the places were found.
        line_locations = chain(
            [start],
            [place.line_location for place in list(places)],
            [end]
        )

        # use the custom iterator, exclude segments where start and end
        # locations are the same. Also exclude segment where 'nxt == None`.
        segments = [(crt, nxt) for crt, nxt
                    in current_and_next(line_locations)
                    if crt != nxt and nxt]

        return segments

    def find_places_in_segment(self, segment, line, max_distance):
        start, end = segment

        # create the Linestring geometry
        subline = LineSubstring(line, start, end)

        # find places within max_distance of the linestring
        places = self.get_places_from_line(subline, max_distance)

        if not places:
            return None

        # iterate over found places to change the line_location
        # from the location on the segment to the location on
        # the original linestring.
        for place in places:
            # relative line location to the start point of the subline
            length = (place.line_location * (end-start))

            # update attribute with line location on the original line
            place.line_location = start + length

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
                ('PKG', 'Parking'),
            )
         ),
        ('Customs', (
                ('C24', 'Customhouse 24h'),
                ('C24LT', 'Customhouse 24h limited'),
                ('CLT', 'Customhouse limited'),
                ('LMK', 'Landmark'),
            )
         ),
        ('Personal', (
                ('HOM', 'Home'),
                ('WRK', 'Work'),
                ('GYM', 'Gym'),
                ('HOL', 'Holiday Place'),
                ('FRD', 'Friend\'s place'),
                ('CST', 'Other place'),
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
            raise ValidationError(
                _("'%(name)s' is not connected to the public transport network."),
                code='invalid',
                params={'name': self.name},
            )

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

    def get_altitude(self):
        """
        return altitude on route as a distance object.
        """
        return D(m=self.altitude_on_route)

    def __str__(self):
        return self.place.name

    def __unicode__(self):
        return self.place.name

    class Meta:
        ordering = ('line_location',)
