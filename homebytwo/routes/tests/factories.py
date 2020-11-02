import json
from pathlib import Path

from django.contrib.gis.geos import Point, fromfile

from factory import Faker, Iterator, LazyAttribute, Sequence, SubFactory
from factory.django import DjangoModelFactory
from faker.providers import BaseProvider
from pandas import DataFrame, read_json
from pytz import utc

from ...routes.models import (Activity, ActivityPerformance, ActivityType, Gear, Place,
                              PlaceType, Route, WebhookTransaction)
from ...utils.factories import AthleteFactory, get_field_choices


class DjangoGeoLocationProvider(BaseProvider):
    """
    https://stackoverflow.com/a/58783744/12427785
    """

    countries = ["CH", "DE", "FR", "IT"]

    def location(self, country=None):
        """
        generate a GeoDjango Point object with a custom Faker provider
        """
        country_code = (
            country or Faker("random_element", elements=self.countries).generate()
        )
        faker = Faker("local_latlng", country_code=country_code, coords_only=True)
        coords = faker.generate()
        return Point(x=float(coords[1]), y=float(coords[0]), srid=4326)


Faker.add_provider(DjangoGeoLocationProvider)


def load_data(file_name):
    return open(get_data_file_path(file_name)).read()


def get_data_file_path(file_name):
    dir_path = Path(__file__).resolve().parent
    return dir_path / "data" / file_name


class GearFactory(DjangoModelFactory):
    class Meta:
        model = Gear

    name = Faker("text", max_nb_chars=50)
    brand_name = Faker("company")
    strava_id = Sequence(lambda n: "g%d" % n)
    athlete = SubFactory(AthleteFactory)


class ActivityTypeFactory(DjangoModelFactory):
    class Meta:
        model = ActivityType
        django_get_or_create = ("name",)

    name = Iterator(ActivityType.SUPPORTED_ACTIVITY_TYPES)


class ActivityPerformanceFactory(DjangoModelFactory):
    class Meta:
        model = ActivityPerformance

    athlete = SubFactory(AthleteFactory)
    activity_type = SubFactory(ActivityTypeFactory)


class PlaceFactory(DjangoModelFactory):
    class Meta:
        model = Place

    place_type = Iterator(PlaceType.objects.all())
    name = Faker("city")
    description = Faker("bs")
    altitude = Faker("random_int", min=0, max=4808)
    geom = Faker("location")
    data_source = Faker("random_element", elements=["geonames", "swissnames3d"])
    source_id = Sequence(lambda n: 1000 + n)


class RouteFactory(DjangoModelFactory):
    class Meta:
        model = Route

    activity_type = SubFactory(ActivityTypeFactory)
    name = Faker("text", max_nb_chars=100)
    source_id = Sequence(lambda n: 1000 + n)
    data_source = "homebytwo"
    description = Faker("bs")
    athlete = SubFactory(AthleteFactory)
    garmin_id = None
    total_elevation_gain = Faker("random_int", min=0, max=5000)
    total_elevation_loss = Faker("random_int", min=0, max=5000)
    total_distance = Faker("random_int", min=1, max=5000)
    geom = fromfile(get_data_file_path("route.ewkb").as_posix())
    start_place = SubFactory(PlaceFactory, geom=Point(geom.coords[0]))
    end_place = SubFactory(PlaceFactory, geom=Point(geom.coords[-1]))
    data = read_json(load_data("route_data.json"), orient="records")


class ActivityFactory(DjangoModelFactory):
    class Meta:
        model = Activity
        exclude = ("streams_json",)

    streams_json = load_data("streams.json")

    name = Faker("sentence")
    description = Faker("bs")
    strava_id = Sequence(lambda n: 1000 + n)
    start_date = Faker("past_datetime", tzinfo=utc)
    athlete = SubFactory(AthleteFactory)
    activity_type = SubFactory(ActivityTypeFactory)
    distance = Faker("random_int", min=500, max=5000)
    total_elevation_gain = Faker("random_int", min=0, max=5000)
    elapsed_time = Faker("time_delta")
    moving_time = elapsed_time
    skip_streams_import = False
    workout_type = Faker(
        "random_element",
        elements=list(get_field_choices(Activity.WORKOUT_TYPE_CHOICES)),
    )
    gear = SubFactory(GearFactory, athlete=athlete)
    streams = DataFrame(
        {stream["type"]: stream["data"] for stream in json.loads(streams_json)}
    )


class WebhookTransactionFactory(DjangoModelFactory):
    class Meta:
        model = WebhookTransaction

    class Params:
        athlete_strava_id = 1000
        activity_strava_id = 1234567890
        action = "create"
        object_type = "activity"

    date_generated = Faker("past_datetime", tzinfo=utc)
    status = WebhookTransaction.UNPROCESSED
    request_meta = {}
    body = LazyAttribute(
        lambda o: {
            "updates": {},
            "owner_id": o.athlete_strava_id,
            "object_id": o.activity_strava_id,
            "event_time": 1600000000,
            "aspect_type": o.action,
            "object_type": o.object_type,
            "subscription_id": 1,
        }
    )
