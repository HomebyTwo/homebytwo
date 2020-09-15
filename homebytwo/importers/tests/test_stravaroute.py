from pathlib import Path

from django.contrib.gis.geos import LineString
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.html import escape

import httpretty
from pandas import DataFrame
from requests.exceptions import ConnectionError
from stravalib import Client as StravaClient

from ...routes.fields import DataFrameField
from ...utils.factories import AthleteFactory, UserFactory
from ...utils.tests import raise_connection_error, read_data
from ..models import StravaRoute
from .factories import StravaRouteFactory

STRAVA_API_BASE_URL = "https://www.strava.com/api/v3/"

CURRENT_DIR = Path(__file__).resolve().parent


class StravaTestCase(TestCase):
    """
    Test the Strava route importer.
    """

    def setUp(self):
        # Add user to the test database and log him in
        self.athlete = AthleteFactory(user__password="testpassword")
        self.client.login(username=self.athlete.user.username, password="testpassword")

    def intercept_get_athlete(
        self,
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
        httpretty.register_uri(
            httpretty.GET,
            athlete_url,
            content_type="application/json",
            body=body,
            status=status,
        )

    ########################
    # Utils and decorators #
    ########################

    def test_get_strava_athlete_success(self):

        # intercept API calls with httpretty
        httpretty.enable(allow_net_connect=False)
        self.intercept_get_athlete()
        self.athlete.strava_client.get_athlete()
        httpretty.disable()

        self.assertIsInstance(self.athlete.strava_client, StravaClient)

    def test_get_strava_athlete_no_connection(self):
        # intercept API calls with httpretty
        httpretty.enable(allow_net_connect=False)
        self.intercept_get_athlete(
            body=raise_connection_error,
        )

        with self.assertRaises(ConnectionError):
            self.athlete.strava_client.get_athlete()

    def test_strava_unauthorized(self):
        httpretty.enable(allow_net_connect=False)
        route_list_api_url = (
            STRAVA_API_BASE_URL + "athletes/%s/routes" % self.athlete.strava_id
        )

        unauthorized_json = read_data(
            "strava_athlete_unauthorized.json", dir_path=CURRENT_DIR
        )

        httpretty.register_uri(
            httpretty.GET,
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

        httpretty.disable

        self.assertRedirects(response, login_url)
        self.assertContains(redirected_response, error)

    def test_strava_connection_error(self):
        httpretty.enable(allow_net_connect=False)
        route_list_api_url = (
            STRAVA_API_BASE_URL + "athletes/%s/routes" % self.athlete.strava_id
        )

        httpretty.register_uri(
            httpretty.GET,
            route_list_api_url,
            content_type="application/json",
            body=raise_connection_error,
        )

        error = "Could not connect to the remote server. Try again later:"
        strava_routes_url = reverse("import_routes", kwargs={"data_source": "strava"})

        response = self.client.get(strava_routes_url, follow=False)
        redirected_response = self.client.get(strava_routes_url, follow=True)

        httpretty.disable

        self.assertRedirects(response, reverse("routes:routes"))
        self.assertContains(redirected_response, error)

    #########
    # Model #
    #########

    def test_get_route_data(self):
        source_id = 2325453

        # intercept url with httpretty
        httpretty.enable(allow_net_connect=False)
        url = STRAVA_API_BASE_URL + "routes/%d/streams" % source_id
        streams_json = read_data("strava_streams.json", dir_path=CURRENT_DIR)

        httpretty.register_uri(
            httpretty.GET,
            url,
            content_type="application/json",
            body=streams_json,
            status=200,
        )

        strava_route = StravaRouteFactory()
        strava_route.geom, strava_route.data = strava_route.get_route_data()
        nb_rows, nb_columns = strava_route.data.shape

        httpretty.disable()

        self.assertIsInstance(strava_route.data, DataFrame)
        self.assertEqual(nb_columns, 2)
        self.assertIsInstance(strava_route.geom, LineString)
        self.assertEqual(strava_route.geom.num_coords, nb_rows)

    def test_set_activity_type(self):
        route = StravaRoute(source_id=2325453, athlete=self.athlete)

        httpretty.enable(allow_net_connect=False)
        # Route details API call
        route_detail_url = STRAVA_API_BASE_URL + "routes/%d" % route.source_id
        route_detail_json = read_data("strava_route_detail.json", dir_path=CURRENT_DIR)

        httpretty.register_uri(
            httpretty.GET,
            route_detail_url,
            content_type="application/json",
            body=route_detail_json,
            status=200,
        )

        route_streams_url = STRAVA_API_BASE_URL + "routes/%d/streams" % route.source_id
        streams_json = read_data("strava_streams.json", dir_path=CURRENT_DIR)

        httpretty.register_uri(
            httpretty.GET,
            route_streams_url,
            content_type="application/json",
            body=streams_json,
            status=200,
        )

        route.get_route_details()
        httpretty.disable()

        self.assertEqual(route.activity_type_id, 1)

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

    def test_strava_routes_success(self):
        self.athlete = AthleteFactory(user__password="testpassword")
        self.client.login(username=self.athlete.user.username, password="testpassword")

        source_name = "Strava"
        route_name = escape("Route Name")
        total_distance = "12.9km"
        total_elevation_gain = "1,880m+"

        # Intercept API calls with httpretty
        httpretty.enable()

        # route list API call with athlete id
        route_list_url = (
            STRAVA_API_BASE_URL + "athletes/%s/routes" % self.athlete.strava_id
        )

        route_list_json = read_data("strava_route_list.json", dir_path=CURRENT_DIR)
        httpretty.register_uri(
            httpretty.GET,
            route_list_url,
            content_type="application/json",
            body=route_list_json,
            status=200,
        )

        url = reverse("import_routes", kwargs={"data_source": "strava"})
        response = self.client.get(url)

        httpretty.disable()

        self.assertContains(response, source_name)
        self.assertContains(response, route_name)
        self.assertContains(response, total_distance)
        self.assertContains(response, total_elevation_gain)

    def test_strava_route_success(self):
        source_id = 2325453

        # intercept API calls with httpretty
        httpretty.enable(allow_net_connect=False)

        # route details API call
        route_detail_url = STRAVA_API_BASE_URL + "routes/%d" % source_id
        route_detail_json = read_data("strava_route_detail.json", dir_path=CURRENT_DIR)

        httpretty.register_uri(
            httpretty.GET,
            route_detail_url,
            content_type="application/json",
            body=route_detail_json,
            status=200,
            match_querystring=False,
        )

        # route streams API call
        route_streams_url = STRAVA_API_BASE_URL + "routes/%d/streams" % source_id
        streams_json = read_data("strava_streams.json", dir_path=CURRENT_DIR)

        httpretty.register_uri(
            httpretty.GET,
            route_streams_url,
            content_type="application/json",
            body=streams_json,
            status=200,
            match_querystring=False,
        )

        url = reverse(
            "import_route", kwargs={"data_source": "strava", "source_id": source_id}
        )
        response = self.client.get(url)
        httpretty.disable()

        route_name = escape("Nom de Route")

        assert response.status_code == 200
        self.assertContains(response, route_name)

    @override_settings(STRAVA_ROUTE_URL="https://example.com/routes/%d")
    def test_display_strava_route_missing_data(self):
        source_id = 4679628
        strava_route = StravaRouteFactory(source_id=source_id, athlete=self.athlete)

        # intercept Strava API call with httpretty
        route_detail_url = STRAVA_API_BASE_URL + "routes/%d" % source_id
        route_detail_json = read_data("strava_route_detail.json", dir_path=CURRENT_DIR)

        httpretty.register_uri(
            httpretty.GET,
            route_detail_url,
            content_type="application/json",
            body=route_detail_json,
            status=200,
        )

        route_streams_url = STRAVA_API_BASE_URL + "routes/%d/streams" % source_id
        route_streams_json = read_data("strava_streams.json", dir_path=CURRENT_DIR)

        httpretty.register_uri(
            httpretty.GET,
            route_streams_url,
            content_type="application/json",
            body=route_streams_json,
            status=200,
        )

        # delete data file
        field = DataFrameField()
        file_path = field.storage.path(strava_route.data.filepath)
        Path(file_path).unlink()

        # intercept API calls with httpretty
        httpretty.enable(allow_net_connect=False)

        # get route page
        response = self.client.get(
            reverse("routes:route", kwargs={"pk": strava_route.id})
        )

        httpretty.disable()

        assert response.status_code == 200

    def test_strava_route_already_imported(self):
        source_id = 22798494
        StravaRouteFactory(
            source_id=source_id,
            athlete=self.athlete,
        )

        # intercept API calls with httpretty
        httpretty.enable(allow_net_connect=False)

        # Route API call
        route_detail_url = STRAVA_API_BASE_URL + "routes/%d" % source_id
        route_detail_json = read_data("strava_route_bike.json", dir_path=CURRENT_DIR)

        httpretty.register_uri(
            httpretty.GET,
            route_detail_url,
            content_type="application/json",
            body=route_detail_json,
            status=200,
        )

        # Streams API call
        stream_url = STRAVA_API_BASE_URL + "routes/%d/streams" % source_id
        streams_json = read_data("strava_streams.json", dir_path=CURRENT_DIR)

        httpretty.register_uri(
            httpretty.GET,
            stream_url,
            content_type="application/json",
            body=streams_json,
            status=200,
        )

        url = reverse(
            "import_route", kwargs={"data_source": "strava", "source_id": source_id}
        )

        response = self.client.get(url)
        httpretty.disable()

        already_imported = "Already Imported"
        self.assertContains(response, already_imported)
