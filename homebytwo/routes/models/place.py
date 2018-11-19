import json
from datetime import datetime
from itertools import chain, islice, tee

import requests
from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.gis.db.models.functions import Distance, LineLocatePoint
from django.contrib.gis.measure import D
from django.core.exceptions import ValidationError

from ...core.models import TimeStampedModel
from ..fields import LineSubstring


def current_and_next(some_iterable):
    """
    using itertools to make current and next item of an iterable available:
    http://stackoverflow.com/questions/1011938/python-previous-and-next-values-inside-a-loop
    """
    items, nexts = tee(some_iterable, 2)
    nexts = chain(islice(nexts, 1, None), [None])
    return zip(items, nexts)


class PlaceManager(models.Manager):
    """
    Manager to retrieve places.
    """

    def get_public_transport(self):
        self.filter(public_transport=True)

    def find_places_along_line(self, line, places, max_distance=75):
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
        found_places = []
        segments = []

        # add places from initial request that found each visited place once
        found_places.extend(places)

        # create segments between the found places
        segments.extend(self.create_segments_from_places(found_places))

        for segment in segments:

            # find additional places along the segment
            new_places = self.find_places_in_segment(segment, line, max_distance, places)

            if new_places:
                start, end = segment
                found_places.extend(new_places)
                segments.extend(
                    self.create_segments_from_places(new_places, start, end)
                )

        found_places.sort(key=lambda o: o.line_location)

        return found_places

    def locate_places_on_line(self, line, max_distance, places=None):
        """
        returns places within a max_distance of a Linestring Geometry
        ordered by, and annotated with the `line_location` and the
        `distance_from_line`:

          * `line_location` is the location on the line expressed as a
            float between 0.0 and 1.0.
          * `distance_from_line` is a geodjango Distance object.

        """

        # line location where we do not want to find additional places
        crop_factor = max_distance / line.length

        # line is shorter than twice the max distance, no place will be found
        if crop_factor >= 0.5:
            return None

        # convert max_distance to Distance object
        max_d = D(m=max_distance)

        # no querystring has been passed to the method, start with all places
        if places is None:
            places = self.all()

        # find all places within max distance from line
        places = places.filter(geom__dwithin=(line, max_d))

        # annotate with distance to line
        places = places.annotate(distance_from_line=Distance('geom', line))

        # annotate with location along the line between 0 and 1
        places = places.annotate(line_location=LineLocatePoint(line, 'geom'))

        # remove start and end places within 1% of start and end location
        places = places.filter(
            line_location__gt=crop_factor,
            line_location__lt=(1-crop_factor),
        )

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

    def find_places_in_segment(self, segment, line, max_distance, places):
        start, end = segment

        # create the Linestring geometry
        subline = LineSubstring(line, start, end)

        # find places within max_distance of the linestring
        places = self.locate_places_on_line(subline, max_distance, places)

        if not places:
            return None

        # iterate over found places to change the line_location
        # from the location on the segment to the location on
        # the original linestring.
        for place in places:
            # relative line location to the start point of the subline
            length = (place.line_location * (end - start))

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


class Place(TimeStampedModel):
    """
    Places are geographic points.
    They have a name, description and geom
    Places are used to create segments from routes and
    and for public transport connection.
    """

    PLACE = 'PLA'
    LOCAL_PLACE = 'LPL'
    SINGLE_BUILDING = 'BDG'
    OPEN_BUILDING = 'OBG'
    TOWER = 'TWR'
    SACRED_BUILDING = 'SBG'
    CHAPEL = 'CPL'
    WAYSIDE_SHRINE = 'SHR'
    MONUMENT = 'MNT'
    FOUNTAIN = 'FTN'
    SUMMIT = 'SUM'
    HILL = 'HIL'
    PASS = 'PAS'
    BELAY = 'BEL'
    WATERFALL = 'WTF'
    CAVE = 'CAV'
    SOURCE = 'SRC'
    BOULDER = 'BLD'
    POINT_OF_VIEW = 'POV'
    BUS_STATION = 'BUS'
    TRAIN_STATION = 'TRA'
    OTHER_STATION = 'OTH'
    BOAT_STATION = 'BOA'
    EXIT = 'EXT'
    ENTRY_AND_EXIT = 'EAE'
    ROAD_PASS = 'RPS'
    INTERCHANGE = 'ICG'
    LOADING_STATION = 'LST'
    PARKING = 'PKG'
    CUSTOMHOUSE_24H = 'C24'
    CUSTOMHOUSE_24H_LIMITED = 'C24LT'
    CUSTOMHOUSE_LIMITED = 'CLT'
    LANDMARK = 'LMK'
    HOME = 'HOM'
    WORK = 'WRK'
    GYM = 'GYM'
    HOLIDAY_PLACE = 'HOL'
    FRIENDS_PLACE = 'FRD'
    OTHER_PLACE = 'CST'

    PLACE_TYPE_CHOICES = (
        (PLACE, 'Place'),
        (LOCAL_PLACE, 'Local Place'),
        ('Constructions', (
            (SINGLE_BUILDING, 'Single Building'),
            (OPEN_BUILDING, 'Open Building'),
            (TOWER, 'Tower'),
            (SACRED_BUILDING, 'Sacred Building'),
            (CHAPEL, 'Chapel'),
            (WAYSIDE_SHRINE, 'Wayside Shrine'),
            (MONUMENT, 'Monument'),
            (FOUNTAIN, 'Fountain'),
        )
        ),
        ('Features', (
            (SUMMIT, 'Summit'),
            (HILL, 'Hill'),
            (PASS, 'Pass'),
            (BELAY, 'Belay'),
            (WATERFALL, 'Waterfall'),
            (CAVE, 'Cave'),
            (SOURCE, 'Source'),
            (BOULDER, 'Boulder'),
            (POINT_OF_VIEW, 'Point of View')
        )
        ),
        ('Public Transport', (
            (BUS_STATION, 'Bus Station'),
            (TRAIN_STATION, 'Train Station'),
            (OTHER_STATION, 'Other Station'),
            (BOAT_STATION, 'Boat Station'),
        )
        ),
        ('Roads', (
            (EXIT, 'Exit'),
            (ENTRY_AND_EXIT, 'Entry and Exit'),
            (ROAD_PASS, 'Road Pass'),
            (INTERCHANGE, 'Interchange'),
            (LOADING_STATION, 'Loading Station'),
            (PARKING, 'Parking'),
        )
        ),
        ('Customs', (
            (CUSTOMHOUSE_24H, 'Customhouse 24h'),
            (CUSTOMHOUSE_24H_LIMITED, 'Customhouse 24h limited'),
            (CUSTOMHOUSE_LIMITED, 'Customhouse limited'),
            (LANDMARK, 'Landmark'),
        )
        ),
        ('Personal', (
            (HOME, 'Home'),
            (WORK, 'Work'),
            (GYM, 'Gym'),
            (HOLIDAY_PLACE, 'Holiday Place'),
            (FRIENDS_PLACE, 'Friend\'s place'),
            (OTHER_PLACE, 'Other place'),
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

    geom = models.PointField(srid=21781)

    objects = PlaceManager()

    class Meta:
        # The pair 'data_source' and 'source_id' should be unique together.
        unique_together = ('data_source', 'source_id',)

    def get_altitude(self):
        return D(m=self.altitude)

    def __str__(self):
        return '{} - {}'.format(
            self.name,
            self.get_place_type_display(),
        )

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
        return '{} - {}'.format(
            self.name,
            self.get_place_type_display(),
        )

    class Meta:
        ordering = ('line_location',)
