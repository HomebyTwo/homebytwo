import os
from pytz import utc

import factory
from django.contrib.gis.geos import GEOSGeometry
from factory.django import DjangoModelFactory
from pandas import read_json

from ...routes.models import (
    Activity,
    ActivityType,
    Gear,
    Place,
    Route,
)
from ...utils.factories import (
    AthleteFactory,
    UserFactory,
    get_field_choices,
)


def load_data(file):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    data_dir = "data"

    json_path = os.path.join(dir_path, data_dir, file,)

    return open(json_path).read()


class GearFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Gear

    name = factory.Faker("text", max_nb_chars=50)
    brand_name = factory.Faker("company")
    strava_id = factory.Sequence(lambda n: "g%d" % n)
    athlete = factory.SubFactory(AthleteFactory)


class ActivityTypeFactory(DjangoModelFactory):
    class Meta:
        model = ActivityType
        django_get_or_create = ("name",)

    name = factory.Faker(
        "random_element",
        elements=list(get_field_choices(ActivityType.ACTIVITY_NAME_CHOICES)),
    )
    slope_squared_param = factory.Faker("pyfloat", min_value=3, max_value=10)
    slope_param = factory.Faker("pyfloat", min_value=0, max_value=1)
    flat_param = factory.Faker("pyfloat", min_value=0, max_value=1)
    total_elevation_gain_param = factory.Faker("pyfloat", min_value=0, max_value=1)


class PlaceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Place

    place_type = factory.Faker(
        "random_element", elements=list(get_field_choices(Place.PLACE_TYPE_CHOICES)),
    )
    name = factory.Faker("city")
    description = factory.Faker("bs")
    altitude = factory.Faker("random_int", min=0, max=4808)
    public_transport = factory.Faker("boolean", chance_of_getting_true=10)
    geom = GEOSGeometry("POINT(0 0)", srid=21781)


class RouteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Route
        exclude = ("route_geojson", "route_data_json")

    route_geojson = load_data("route_geom.json")
    route_data_json = load_data("route_data.json")

    activity_type = factory.SubFactory(ActivityTypeFactory)
    name = factory.Faker("text", max_nb_chars=100)
    source_id = factory.Sequence(lambda n: "%d" % n)
    data_source = "homebytwo"
    description = factory.Faker("bs")
    owner = factory.SubFactory(UserFactory)
    totalup = factory.Faker("random_int", min=0, max=5000)
    totaldown = factory.Faker("random_int", min=0, max=5000)
    length = factory.Faker("random_int", min=1, max=5000)
    geom = GEOSGeometry(route_geojson, srid=21781)
    start_place = factory.SubFactory(
        PlaceFactory, geom="POINT (%s %s)" % geom.coords[0]
    )
    end_place = factory.SubFactory(PlaceFactory, geom="POINT (%s %s)" % geom.coords[-1])
    data = read_json(route_data_json, orient="records")


class ActivityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Activity

    name = factory.Faker("sentence")
    description = factory.Faker("bs")
    strava_id = factory.Sequence(lambda n: "100%d" % n)
    start_date = factory.Faker("past_datetime", tzinfo=utc)
    athlete = factory.SubFactory(AthleteFactory)
    activity_type = factory.SubFactory(ActivityTypeFactory)
    manual = False
    distance = factory.Faker("random_int", min=500, max=5000)
    totalup = factory.Faker("random_int", min=0, max=5000)
    elapsed_time = factory.Faker("time_delta")
    moving_time = elapsed_time
    workout_type = factory.Faker(
        "random_element",
        elements=list(get_field_choices(Activity.WORKOUT_TYPE_CHOICES)),
    )
    gear = factory.SubFactory(GearFactory)
