from pathlib import Path

from django.contrib.gis.geos import LineString, Point
from django.shortcuts import resolve_url
from django.urls import reverse
from django.utils.html import escape
from django.utils.http import urlencode

import pytest
import responses
from pandas import DataFrame
from pytest_django.asserts import assertContains, assertRedirects
from requests.exceptions import ConnectionError
from stravalib import Client as StravaClient

from ...conftest import STRAVA_API_BASE_URL
from ...routes.fields import DataFrameField
from ...routes.models import ActivityType
from ...routes.tests.factories import PlaceFactory, ActivityFactory, ActivityTypeFactory
from ...utils.factories import AthleteFactory
from ...utils.tests import get_route_post_data
from ..models import StravaRoute
from .factories import StravaRouteFactory

CURRENT_DIR = Path(__file__).resolve().parent


@pytest.fixture
def mock_get_athlete_response(mock_json_response):
    mock_json_response(
        url=STRAVA_API_BASE_URL + "athlete", response_file="strava_athlete.json"
    )


########################
# Utils and decorators #
########################


def test_get_strava_athlete_success(athlete, mock_get_athlete_response):
    mock_get_athlete_response
    athlete.strava_client.get_athlete()
    assert isinstance(athlete.strava_client, StravaClient)


@responses.activate
def test_get_strava_athlete_no_connection(athlete):
    with pytest.raises(ConnectionError):
        athlete.strava_client.get_athlete()


#########
# Model #
#########


def test_strava_get_or_stub_new(athlete):
    source_id = 123456789
    route, update = StravaRoute.get_or_stub(source_id=source_id, athlete=athlete)

    assert route.data_source == "strava"
    assert route.source_id == source_id
    assert route.athlete == athlete
    assert not update
    assert not route.pk


def test_strava_get_or_stub_existing(athlete):
    existing_route = StravaRouteFactory(athlete=athlete)
    retrieved_route, update = StravaRoute.get_or_stub(
        source_id=existing_route.source_id, athlete=athlete
    )

    assert retrieved_route.data_source == "strava"
    assert retrieved_route.source_id == existing_route.source_id
    assert retrieved_route.athlete == athlete
    assert update
    assert retrieved_route.pk


def test_get_route_data(athlete, mock_strava_streams_response):
    source_id = 2325453

    mock_strava_streams_response(source_id=source_id)
    strava_route = StravaRouteFactory.build(athlete=athlete, source_id=source_id)
    strava_route.geom, strava_route.data = strava_route.get_route_data()

    nb_rows, nb_columns = strava_route.data.shape
    assert isinstance(strava_route.data, DataFrame)
    assert nb_columns == 2
    assert isinstance(strava_route.geom, LineString)
    assert strava_route.geom.num_coords == nb_rows


def test_set_activity_type_ride(athlete, mock_route_details_response):
    route = StravaRoute(source_id=2325453, athlete=athlete)

    mock_route_details_response(
        route.data_source, route.source_id, api_response_json="strava_route_bike.json"
    )
    route.get_route_details()

    assert route.activity_type.name == ActivityType.RIDE


########################
# views: import_routes #
########################


def test_redirect_when_strava_token_missing(athlete, client, mock_routes_response):
    asocial_athlete = AthleteFactory(
        user__password="test_password", user__social_auth=None
    )
    client.login(username=asocial_athlete.user.username, password="test_password")

    routes_url = resolve_url("import_routes", data_source="strava")
    response = client.get(routes_url)
    login_url = "{url}?{params}".format(
        url=reverse("login"), params=urlencode({"next": routes_url})
    )

    assertRedirects(response, login_url)


def test_get_strava_routes(athlete, client, mock_routes_response):

    source_name = "Strava"
    route_name = escape("Route Name")
    total_distance = "12.9km"
    total_elevation_gain = "1,880m+"

    mock_routes_response(athlete, "strava")
    url = resolve_url("import_routes", data_source="strava")
    response = client.get(url)

    assertContains(response, source_name)
    assertContains(response, route_name)
    assertContains(response, total_distance)
    assertContains(response, total_elevation_gain)


def test_get_strava_routes_unauthorized(client, athlete, mock_routes_response):

    mock_routes_response(
        athlete, "strava", response_file="strava_unauthorized.json", status=401
    )

    strava_routes_url = resolve_url("import_routes", data_source="strava")
    login_url = "{url}?{params}".format(
        url=reverse("login"), params=urlencode({"next": strava_routes_url})
    )

    error = "There was an issue connecting to Strava. Try again later!"
    response = client.get(strava_routes_url, follow=False)
    redirected_response = client.get(strava_routes_url, follow=True)

    assertRedirects(response, login_url)
    assertContains(redirected_response, error)


@responses.activate
def test_get_strava_routes_connection_error(athlete, client):
    error = "Could not connect to the remote server. Try again later:"
    strava_routes_url = resolve_url("import_routes", data_source="strava")

    response = client.get(strava_routes_url, follow=False)
    redirected_response = client.get(strava_routes_url, follow=True)

    assertRedirects(response, reverse("routes:routes"))
    assertContains(redirected_response, error)


#######################
# views: import_route #
#######################


def test_get_import_strava_route(athlete, mock_import_route_call_response):

    response = mock_import_route_call_response("strava")
    route_name = escape("Le Flon - Col de Verne")

    assert response.status_code == 200
    assertContains(response, route_name)


def test_get_import_strava_route_with_checkpoints(
    athlete, mock_import_route_call_response
):
    place = PlaceFactory(geom=Point(x=759599.4425849458, y=5833329.401508623))
    response = mock_import_route_call_response("strava")

    assertContains(response, place.name)


def test_get_import_strava_route_already_imported(
    athlete, mock_import_route_call_response
):
    route = StravaRouteFactory(
        source_id=22798494,
        athlete=athlete,
    )

    response = mock_import_route_call_response(
        data_source=route.data_source,
        source_id=route.source_id,
    )

    content = "Update"
    assertContains(response, content)


def test_post_import_strava_route_already_imported(
    athlete, mock_import_route_call_response
):
    run = ActivityType.objects.get(name="Run")
    ActivityFactory(athlete=athlete, activity_type=run)
    route = StravaRouteFactory(source_id=22798494, athlete=athlete, activity_type=run)

    response = mock_import_route_call_response(
        data_source=route.data_source,
        source_id=route.source_id,
        method="post",
        post_data=get_route_post_data(route),
        follow_redirect=True,
    )

    content = "updated"
    assertRedirects(response, route.get_absolute_url())
    assertContains(response, content)


def test_post_import_strava_route_bad_distance(
    athlete,
    mock_import_route_call_response,
):
    route = StravaRouteFactory.build(
        athlete=athlete, activity_type=ActivityTypeFactory()
    )
    ActivityFactory(athlete=athlete, activity_type=route.activity_type)
    post_data = get_route_post_data(route)
    response = mock_import_route_call_response(
        route.data_source,
        route.source_id,
        api_streams_json="bad_strava_streams.json",
        method="post",
        post_data=post_data,
    )
    error = "Cannot clean track data: invalid distance values."
    message = f"Route cannot be imported: {error}."

    assert response.status_code == 200
    assertContains(response, message)


############################
# views: routes:view_route #
############################


def test_display_strava_route_missing_data(
    athlete, client, mock_strava_streams_response
):
    route = StravaRouteFactory(source_id=1234567, athlete=athlete)
    mock_strava_streams_response(source_id=route.source_id)

    # delete data file
    field = DataFrameField()
    file_path = field.storage.path(route.data.filepath)
    Path(file_path).unlink()

    # get route page
    response = client.get(route.get_absolute_url())

    assert response.status_code == 200
