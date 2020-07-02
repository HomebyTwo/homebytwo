from pathlib import Path

from django.contrib.gis.geos import GEOSGeometry, Point

from factory import Faker, Sequence, SubFactory
from factory.django import DjangoModelFactory
from faker.providers import BaseProvider
from pandas import read_json
from pytz import utc

from ...routes.models import (
    Activity,
    ActivityType,
    Gear,
    Place,
    Route,
    WebhookTransaction,
)
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


def load_data(file):
    dir_path = Path(__file__).resolve().parent
    json_path = dir_path / "data" / file

    return open(json_path).read()


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

    name = Faker(
        "random_element",
        elements=list(get_field_choices(ActivityType.ACTIVITY_NAME_CHOICES)),
    )
    slope_squared_param = Faker("pyfloat", min_value=3, max_value=10)
    slope_param = Faker("pyfloat", min_value=0, max_value=1)
    flat_param = Faker("pyfloat", min_value=0, max_value=1)
    total_elevation_gain_param = Faker("pyfloat", min_value=0, max_value=1)


class PlaceFactory(DjangoModelFactory):
    class Meta:
        model = Place

    place_type = Faker(
        "random_element", elements=list(get_field_choices(Place.PLACE_TYPE_CHOICES)),
    )
    name = Faker("city")
    description = Faker("bs")
    altitude = Faker("random_int", min=0, max=4808)
    public_transport = Faker("boolean", chance_of_getting_true=10)
    geom = Faker("location")


class RouteFactory(DjangoModelFactory):
    class Meta:
        model = Route
        exclude = ("route_geojson", "route_data_json")

    route_geojson = load_data("route_geom.json")
    route_data_json = load_data("route_data.json")

    activity_type = SubFactory(ActivityTypeFactory)
    name = Faker("text", max_nb_chars=100)
    source_id = Sequence(lambda n: "%d" % n)
    data_source = "homebytwo"
    description = Faker("bs")
    athlete = SubFactory(AthleteFactory)
    garmin_id = None
    totalup = Faker("random_int", min=0, max=5000)
    totaldown = Faker("random_int", min=0, max=5000)
    length = Faker("random_int", min=1, max=5000)
    geom = GEOSGeometry(route_geojson, srid=21781)
    start_place = SubFactory(PlaceFactory, geom=Point(geom.coords[0]))
    end_place = SubFactory(PlaceFactory, geom=Point(geom.coords[-1]))
    data = read_json(route_data_json, orient="records")


class ActivityFactory(DjangoModelFactory):
    class Meta:
        model = Activity

    name = Faker("sentence")
    description = Faker("bs")
    strava_id = Sequence(lambda n: "100%d" % n)
    start_date = Faker("past_datetime", tzinfo=utc)
    athlete = SubFactory(AthleteFactory)
    activity_type = SubFactory(ActivityTypeFactory)
    manual = False
    distance = Faker("random_int", min=500, max=5000)
    totalup = Faker("random_int", min=0, max=5000)
    elapsed_time = Faker("time_delta")
    moving_time = elapsed_time
    workout_type = Faker(
        "random_element",
        elements=list(get_field_choices(Activity.WORKOUT_TYPE_CHOICES)),
    )
    gear = SubFactory(GearFactory)


class WebhookTransactionFactory(DjangoModelFactory):
    class Meta:
        model = WebhookTransaction

    date_generated = Faker("past_datetime", tzinfo=utc)
    status = WebhookTransaction.UNPROCESSED
    request_meta = {}
    body = {
        "updates": {"title": "Messy"},
        "owner_id": 0,
        "object_id": 0,
        "event_time": 0,
        "aspect_type": "update",
        "object_type": "activity",
        "subscription_id": 0,
    }
