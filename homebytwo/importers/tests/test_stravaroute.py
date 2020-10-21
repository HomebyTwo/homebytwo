from pathlib import Path

from django.contrib.gis.geos import LineString
from django.forms import model_to_dict
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.html import escape

import responses
from pandas import DataFrame
from pytest_django.asserts import assertContains
from requests.exceptions import ConnectionError
from stravalib import Client as StravaClient

from ...conftest import STRAVA_API_BASE_URL
from ...routes.fields import DataFrameField
from ...routes.forms import RouteForm
from ...utils.factories import AthleteFactory, UserFactory
from ...utils.tests import read_data
from ..models import StravaRoute
from .factories import StravaRouteFactory

CURRENT_DIR = Path(__file__).resolve().parent


def intercept_get_athlete(
    body=read_data("strava_athlete.json", dir_path=CURRENT_DIR),
    status=200,
):
    """
    intercept the Strava API call to get_athlete. This call is made
    when creating the strava client to test if the API is
    available.
    """

    # athlete API call
    athlete_url = STRAVA_API_BASE_URL + "athlete"
    responses.add(
        responses.GET,
        athlete_url,
        content_type="application/json",
        body=body,
        status=status,
    )


class StravaTestCase(TestCase):
    """
    Test the Strava route importer.
    """

    def setUp(self):
        # Add user to the test database and log him in
        self.athlete = AthleteFactory(user__password="testpassword")
        self.client.login(username=self.athlete.user.username, password="testpassword")

    ########################
    # Utils and decorators #
    ########################

    @responses.activate
    def test_get_strava_athlete_success(self):

        # intercept API calls with responses
        intercept_get_athlete()
        self.athlete.strava_client.get_athlete()
        self.assertIsInstance(self.athlete.strava_client, StravaClient)

    @responses.activate
    def test_get_strava_athlete_no_connection(self):
        # intercept API calls with responses
        intercept_get_athlete(
            body=ConnectionError("Connection error."),
        )

        with self.assertRaises(ConnectionError):
            self.athlete.strava_client.get_athlete()

    @responses.activate
    def test_strava_unauthorized(self):
        route_list_api_url = (
            STRAVA_API_BASE_URL + "athletes/%s/routes" % self.athlete.strava_id
        )

        unauthorized_json = read_data(
            "strava_athlete_unauthorized.json", dir_path=CURRENT_DIR
        )

        responses.add(
            responses.GET,
            route_list_api_url,
            content_type="application/json",
            body=unauthorized_json,
            status=401,
        )

        strava_routes_url = reverse("import_routes", kwargs={"data_source": "strava"})
        login_url = "{url}?next={next}".format(
            url=reverse("login"), next=strava_routes_url
        )
        error = "There was an issue connecting to Strava. Try again later!"
        response = self.client.get(strava_routes_url, follow=False)
        redirected_response = self.client.get(strava_routes_url, follow=True)

        self.assertRedirects(response, login_url)
        self.assertContains(redirected_response, error)

    @responses.activate
    def test_strava_connection_error(self):
        route_list_api_url = (
            STRAVA_API_BASE_URL + "athletes/%s/routes" % self.athlete.strava_id
        )

        responses.add(
            responses.GET,
            route_list_api_url,
            content_type="application/json",
            body=ConnectionError("Connection error."),
        )

        error = "Could not connect to the remote server. Try again later:"
        strava_routes_url = reverse("import_routes", kwargs={"data_source": "strava"})

        response = self.client.get(strava_routes_url, follow=False)
        redirected_response = self.client.get(strava_routes_url, follow=True)

        self.assertRedirects(response, reverse("routes:routes"))
        self.assertContains(redirected_response, error)

    #########
    # Model #
    #########

    @responses.activate
    def test_get_route_data(self):
        source_id = 2325453

        # intercept url with responses
        url = STRAVA_API_BASE_URL + "routes/%d/streams" % source_id
        streams_json = read_data("strava_streams.json", dir_path=CURRENT_DIR)

        responses.add(
            responses.GET,
            url,
            content_type="application/json",
            body=streams_json,
            status=200,
        )

        strava_route = StravaRouteFactory(source_id=source_id)
        strava_route.geom, strava_route.data = strava_route.get_route_data()
        nb_rows, nb_columns = strava_route.data.shape

        self.assertIsInstance(strava_route.data, DataFrame)
        self.assertEqual(nb_columns, 2)
        self.assertIsInstance(strava_route.geom, LineString)
        self.assertEqual(strava_route.geom.num_coords, nb_rows)

    @responses.activate
    def test_set_activity_type(self):
        route = StravaRoute(source_id=2325453, athlete=self.athlete)

        # Route details API call
        route_detail_url = STRAVA_API_BASE_URL + "routes/%d" % route.source_id
        route_detail_json = read_data("strava_route_detail.json", dir_path=CURRENT_DIR)

        responses.add(
            responses.GET,
            route_detail_url,
            content_type="application/json",
            body=route_detail_json,
            status=200,
        )

        route_streams_url = STRAVA_API_BASE_URL + "routes/%d/streams" % route.source_id
        streams_json = read_data("strava_streams.json", dir_path=CURRENT_DIR)

        responses.add(
            responses.GET,
            route_streams_url,
            content_type="application/json",
            body=streams_json,
            status=200,
        )

        route.get_route_details()

        self.assertEqual(route.activity_type_id, 1)

    def test_strava_get_or_stub_new(self):
        source_id = 123456789
        route, update = StravaRoute.get_or_stub(
            source_id=source_id, athlete=self.athlete
        )

        assert route.data_source == "strava"
        assert route.source_id == source_id
        assert route.athlete == self.athlete
        assert not update
        assert not route.pk

    def test_strava_get_or_stub_existing(self):
        existing_route = StravaRouteFactory(athlete=self.athlete)
        retrieved_route, update = StravaRoute.get_or_stub(
            source_id=existing_route.source_id, athlete=self.athlete
        )

        assert retrieved_route.data_source == "strava"
        assert retrieved_route.source_id == existing_route.source_id
        assert retrieved_route.athlete == self.athlete
        assert update
        assert retrieved_route.pk

    #########
    # views #
    #########

    def test_redirect_when_strava_token_missing(self):
        asocial_user = UserFactory(password="testpassword")
        self.client.login(username=asocial_user, password="testpassword")

        routes_url = reverse("import_routes", kwargs={"data_source": "strava"})
        response = self.client.get(routes_url)
        login_url = "{url}?next={next}".format(url=reverse("login"), next=routes_url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, login_url)

    @responses.activate
    def test_strava_routes_success(self):
        self.athlete = AthleteFactory(user__password="testpassword")
        self.client.login(username=self.athlete.user.username, password="testpassword")

        source_name = "Strava"
        route_name = escape("Route Name")
        total_distance = "12.9km"
        total_elevation_gain = "1,880m+"

        # route list API call with athlete id
        route_list_url = (
            STRAVA_API_BASE_URL + "athletes/%s/routes" % self.athlete.strava_id
        )

        route_list_json = read_data("strava_route_list.json", dir_path=CURRENT_DIR)
        responses.add(
            responses.GET,
            route_list_url,
            content_type="application/json",
            body=route_list_json,
            status=200,
        )

        url = reverse("import_routes", kwargs={"data_source": "strava"})
        response = self.client.get(url)

        self.assertContains(response, source_name)
        self.assertContains(response, route_name)
        self.assertContains(response, total_distance)
        self.assertContains(response, total_elevation_gain)

    @responses.activate
    @override_settings(STRAVA_ROUTE_URL="https://example.com/routes/%d")
    def test_display_strava_route_missing_data(self):
        source_id = 4679628
        strava_route = StravaRouteFactory(source_id=source_id, athlete=self.athlete)

        # intercept Strava API call with responses
        route_detail_url = STRAVA_API_BASE_URL + "routes/%d" % source_id
        route_detail_json = read_data("strava_route_detail.json", dir_path=CURRENT_DIR)

        responses.add(
            responses.GET,
            route_detail_url,
            content_type="application/json",
            body=route_detail_json,
            status=200,
        )

        route_streams_url = STRAVA_API_BASE_URL + "routes/%d/streams" % source_id
        route_streams_json = read_data("strava_streams.json", dir_path=CURRENT_DIR)

        responses.add(
            responses.GET,
            route_streams_url,
            content_type="application/json",
            body=route_streams_json,
            status=200,
        )

        # delete data file
        field = DataFrameField()
        file_path = field.storage.path(strava_route.data.filepath)
        Path(file_path).unlink()

        # get route page
        response = self.client.get(
            reverse("routes:route", kwargs={"pk": strava_route.id})
        )

        assert response.status_code == 200

    @responses.activate
    def test_strava_route_already_imported(self):
        source_id = 22798494
        StravaRouteFactory(
            source_id=source_id,
            athlete=self.athlete,
        )

        # Route API call
        route_detail_url = STRAVA_API_BASE_URL + "routes/%d" % source_id
        route_detail_json = read_data("strava_route_bike.json", dir_path=CURRENT_DIR)

        responses.add(
            responses.GET,
            route_detail_url,
            content_type="application/json",
            body=route_detail_json,
            status=200,
        )

        # Streams API call
        stream_url = STRAVA_API_BASE_URL + "routes/%d/streams" % source_id
        streams_json = read_data("strava_streams.json", dir_path=CURRENT_DIR)

        responses.add(
            responses.GET,
            stream_url,
            content_type="application/json",
            body=streams_json,
            status=200,
        )

        url = reverse(
            "import_route", kwargs={"data_source": "strava", "source_id": source_id}
        )

        response = self.client.get(url)
        content = "Update"
        self.assertContains(response, content)


def test_strava_route_success(athlete, mock_import_route_response_call):
    source_id = 2325453

    response = mock_import_route_response_call("strava", source_id)
    route_name = escape("Nom de Route")

    assert response.status_code == 200
    assertContains(response, route_name)


def test_import_strava_route_bad_distance(
    athlete,
    client,
    mock_import_route_response_call,
):
    route = StravaRouteFactory.build(
        athlete=athlete,
        start_place=None,
        end_place=None,
    )

    post_data = dict(
        filter(
            lambda item: item[0] in RouteForm.Meta.fields and item[1],
            model_to_dict(route).items(),
        )
    )
    post_data["activity_type"] = 1
    response = mock_import_route_response_call(
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
