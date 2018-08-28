import os

import factory
import factory.django
import factory.fuzzy
from django.contrib.gis.geos import GEOSGeometry
from pandas import read_json

from ...routes import models
from ...utils.factories import UserFactory


def load_data(file):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        data_dir = 'data'

        json_path = os.path.join(
            dir_path,
            data_dir,
            file,
        )

        return open(json_path).read()


class ActivityTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.ActivityType
    name = factory.fuzzy.FuzzyText()
    slope_squared_param = factory.fuzzy.FuzzyFloat(3.0, 10.0)
    slope_param = factory.fuzzy.FuzzyFloat(0.2, 1.2)
    flat_param = factory.fuzzy.FuzzyFloat(0.20, 1.0)
    total_elevation_gain_param = factory.fuzzy.FuzzyFloat(0.05, 1.05)


class PlaceFactory(factory.django.DjangoModelFactory):

    class Meta:
        model = models.Place
        exclude = ['place_types']

    place_types = [
        models.Place.PLACE,
        models.Place.SINGLE_BUILDING,
        models.Place.OPEN_BUILDING,
        models.Place.TOWER,
        models.Place.SACRED_BUILDING,
        models.Place.CHAPEL,
        models.Place.WAYSIDE_SHRINE,
        models.Place.MONUMENT,
        models.Place.FOUNTAIN,
        models.Place.SUMMIT,
        models.Place.HILL,
        models.Place.PASS,
        models.Place.BELAY,
        models.Place.WATERFALL,
        models.Place.CAVE,
        models.Place.SOURCE,
        models.Place.BOULDER,
        models.Place.POINT_OF_VIEW,
        models.Place.BUS_STATION,
        models.Place.TRAIN_STATION,
        models.Place.OTHER_STATION,
        models.Place.BOAT_STATION,
        models.Place.EXIT,
        models.Place.ENTRY_AND_EXIT,
        models.Place.ROAD_PASS,
        models.Place.INTERCHANGE,
        models.Place.LOADING_STATION,
        models.Place.PARKING,
        models.Place.CUSTOMHOUSE_24H,
        models.Place.CUSTOMHOUSE_24H_LIMITED,
        models.Place.CUSTOMHOUSE_LIMITED,
        models.Place.LANDMARK,
        models.Place.HOME,
        models.Place.WORK,
        models.Place.GYM,
        models.Place.HOLIDAY_PLACE,
        models.Place.FRIENDS_PLACE,
        models.Place.OTHER_PLACE,
    ]

    place_type = factory.fuzzy.FuzzyChoice(place_types)
    name = factory.fuzzy.FuzzyText()
    description = factory.fuzzy.FuzzyText(length=100)
    altitude = factory.fuzzy.FuzzyInteger(5000)
    public_transport = factory.Iterator([True, False])
    geom = GEOSGeometry('POINT(0 0)', srid=21781)


class RouteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Route
        exclude = ('route_geojson', 'route_data_json')

    route_geojson = load_data('route_geom.json')
    route_data_json = load_data('route_data.json')

    activity_type = factory.SubFactory(ActivityTypeFactory)
    name = factory.fuzzy.FuzzyText()
    source_id = factory.Sequence(lambda n: '%d' % n)
    data_source = 'homebytwo'
    description = factory.fuzzy.FuzzyText(length=100)
    owner = factory.SubFactory(UserFactory)
    totalup = factory.fuzzy.FuzzyInteger(5000)
    totaldown = factory.fuzzy.FuzzyInteger(5000)
    length = factory.fuzzy.FuzzyInteger(50000)
    geom = GEOSGeometry(route_geojson, srid=21781)
    start_place = factory.SubFactory(
        PlaceFactory,
        geom='POINT (%s %s)' % geom.coords[0]
    )
    end_place = factory.SubFactory(
        PlaceFactory,
        geom='POINT (%s %s)' % geom.coords[-1]
    )
    data = read_json(route_data_json, orient='records')
