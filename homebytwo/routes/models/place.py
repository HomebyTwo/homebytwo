import json
from datetime import datetime
from itertools import chain, islice, tee

import requests
from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.gis.measure import D
from django.core.exceptions import ValidationError

from ...core.models import TimeStampedModel


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
                "'%(name)s' is not connected to the public transport network.",
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
