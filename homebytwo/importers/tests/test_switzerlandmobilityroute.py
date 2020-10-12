from json import loads as json_loads
from os.path import dirname, realpath
from pathlib import Path
from re import compile as re_compile

from django.conf import settings
from django.contrib.gis.geos import LineString, Point
from django.forms.models import model_to_dict
from django.shortcuts import resolve_url
from django.test import TestCase, override_settings
from django.urls import reverse

import responses
from django.utils.http import urlencode
from requests.exceptions import ConnectionError

from ...routes.fields import DataFrameField
from ...routes.forms import RouteForm
from ...routes.models import Checkpoint
from ...routes.tests.factories import PlaceFactory
from ...utils.factories import AthleteFactory, UserFactory
from ...utils.tests import read_data
from ..exceptions import SwitzerlandMobilityError, SwitzerlandMobilityMissingCredentials
from ..forms import SwitzerlandMobilityLogin
from ..models import SwitzerlandMobilityRoute
from ..models.switzerlandmobilityroute import request_json
from ..utils import split_routes
from .factories import SwitzerlandMobilityRouteFactory

CURRENT_DIR = dirname(realpath(__file__))


@override_settings(
    SWITZERLAND_MOBILITY_LOGIN_URL="https://example.com/login",
    SWITZERLAND_MOBILITY_LIST_URL="https://example.com/tracks",
    SWITZERLAND_MOBILITY_META_URL="https://example.com/track/%d/getmeta",
    SWITZERLAND_MOBILITY_ROUTE_DATA_URL="https://example.com/track/%d/show",
    SWITZERLAND_MOBILITY_ROUTE_URL="https://example.com/?trackId=%d",
)
class SwitzerlandMobilityTestCase(TestCase):
    """
    Test the Switzerland Mobility route importer
    """

    def setUp(self):
        # Add athlete to the test database and log him in
        self.athlete = AthleteFactory(user__password="test_password")
        self.client.login(username=self.athlete.user.username, password="test_password")

        # add Switzerland Mobility cookies to the session
        session = self.client.session
        session["switzerland_mobility_cookies"] = {
            "mf-chmobil": "xxx",
            "srv": "yyy",
        }
        session.save()

    @responses.activate
    def get_import_route_response(
        self,
        route_id,
        response_file="2191833_show.json",
        status=200,
        content_type="application/json",
        method="get",
        post_data=None,
    ):
        url = reverse(
            "import_route",
            kwargs={"data_source": "switzerland_mobility", "source_id": route_id},
        )

        data_url = settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL % route_id
        body = read_data(file=response_file, dir_path=CURRENT_DIR)

        # intercept call to Switzerland Mobility with responses
        responses.add(
            method=responses.GET,
            url=data_url,
            content_type=content_type,
            body=body,
            status=status,
        )

        if method == "get":
            return self.client.get(url)
        if method == "post":
            return self.client.post(url, post_data)

    #########
    # Model #
    #########

    @responses.activate
    def test_request_json_success(self):
        cookies = self.client.session["switzerland_mobility_cookies"]

        url = "https://testurl.ch"

        # intercept call with responses
        body = '[123456, "Test", null]'

        responses.add(
            responses.GET, url, content_type="application/json", body=body, status=200
        )

        json_response = request_json(url, cookies)

        self.assertEqual(json_loads(body), json_response)

    @responses.activate
    def test_request_json_server_error(self):
        cookies = self.client.session["switzerland_mobility_cookies"]

        url = "https://testurl.ch"

        # intercept call with responses
        html_response = read_data(file="500.html", dir_path=CURRENT_DIR)

        responses.add(
            responses.GET, url, content_type="text/html", body=html_response, status=500
        )
        with self.assertRaises(SwitzerlandMobilityError):
            request_json(url, cookies)

    @responses.activate
    def test_request_json_connection_error(self):
        cookies = self.client.session["switzerland_mobility_cookies"]
        url = "https://testurl.ch"

        # intercept call with responses

        responses.add(
            responses.GET,
            url,
            body=ConnectionError("Connection error."),
        )
        with self.assertRaises(ConnectionError):
            request_json(url, cookies)

    @responses.activate
    def test_get_remote_raw_routes_success(self):
        # intercept call to map.wanderland.ch with responses
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        json_response = read_data("tracks_list.json", dir_path=CURRENT_DIR)

        responses.add(
            responses.GET,
            routes_list_url,
            content_type="application/json",
            body=json_response,
            status=200,
        )
        manager = SwitzerlandMobilityRoute.objects
        remote_routes = manager.get_remote_routes_list(
            athlete=self.athlete,
            cookies=self.client.session.get("switzerland_mobility_cookies"),
        )

        self.assertEqual(len(remote_routes), 82)

    @responses.activate
    def test_get_remote_routes_empty(self):
        # create user
        user = UserFactory()

        # intercept call to map.wanderland.ch with responses
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        json_response = "[]"

        responses.add(
            responses.GET,
            routes_list_url,
            content_type="application/json",
            body=json_response,
            status=200,
        )
        manager = SwitzerlandMobilityRoute.objects
        remote_routes = manager.get_remote_routes_list(
            athlete=user.athlete,
            cookies=self.client.session.get("switzerland_mobility_cookies"),
        )

        self.assertEqual(len(remote_routes), 0)

    @responses.activate
    def test_get_remote_routes_list_server_error(self):
        # create user
        user = UserFactory()

        # intercept call to map.wanderland.ch with responses
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        json_response = "[]"

        responses.add(
            responses.GET,
            routes_list_url,
            content_type="application/json",
            body=json_response,
            status=500,
        )

        routes_manager = SwitzerlandMobilityRoute.objects
        with self.assertRaises(SwitzerlandMobilityError):
            routes_manager.get_remote_routes_list(
                athlete=user.athlete,
                cookies=self.client.session.get("switzerland_mobility_cookies"),
            )

    @responses.activate
    def test_get_remote_routes_list_connection_error(self):
        # create user
        athlete = self.athlete

        # intercept call to map.wanderland.ch with responses
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL

        responses.add(
            responses.GET,
            routes_list_url,
            content_type="application/json",
            body=ConnectionError("Connection error."),
        )

        manager = SwitzerlandMobilityRoute.objects
        with self.assertRaises(ConnectionError):
            manager.get_remote_routes_list(
                athlete=athlete,
                cookies=self.client.session.get("switzerland_mobility_cookies"),
            )

    def test_check_for_existing_routes_success(self):

        # save an existing route
        SwitzerlandMobilityRouteFactory(
            source_id=2191833,
            name="Haute Cime",
            athlete=self.athlete,
        )

        # save a route not on the remote
        SwitzerlandMobilityRouteFactory(source_id=1234567, athlete=self.athlete)

        remote_routes = [
            SwitzerlandMobilityRouteFactory.build(
                name="Haute Cime",
                athlete=self.athlete,
                source_id=2191833,
            ),
            SwitzerlandMobilityRouteFactory.build(
                name="Grammont",
                athlete=self.athlete,
                source_id=2433141,
            ),
            SwitzerlandMobilityRouteFactory.build(
                name="Rochers de Nayes",
                athlete=self.athlete,
                source_id=2692136,
            ),
            SwitzerlandMobilityRouteFactory.build(
                name="Villeneuve - Leysin",
                athlete=self.athlete,
                source_id=3011765,
            ),
        ]

        local_routes = SwitzerlandMobilityRoute.objects.for_user(self.athlete.user)
        new_routes, existing_routes, deleted_routes = split_routes(
            remote_routes, local_routes
        )

        self.assertEqual(len(new_routes), 3)
        self.assertEqual(len(existing_routes), 1)
        self.assertEqual(len(deleted_routes), 1)

    @responses.activate
    def test_get_remote_routes_list_success(self):

        # save an existing route
        SwitzerlandMobilityRouteFactory(athlete=self.athlete)

        # intercept routes_list call to map.wanderland.ch with responses
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        json_response = read_data("tracks_list.json", dir_path=CURRENT_DIR)

        responses.add(
            responses.GET,
            routes_list_url,
            content_type="application/json",
            body=json_response,
            status=200,
        )

        # intercept call to map.wanderland.ch with responses
        # remove "https://
        route_meta_url = settings.SWITZERLAND_MOBILITY_META_URL[8:]
        # Turn the route meta URL into a regular expression
        route_meta_url = re_compile(route_meta_url.replace("%d", r"(\w+)"))

        route_json = read_data("track_info.json", dir_path=CURRENT_DIR)

        responses.add(
            responses.GET,
            route_meta_url,
            content_type="application/json",
            body=route_json,
            status=200,
        )

        remote_routes = SwitzerlandMobilityRoute.objects.get_remote_routes_list(
            athlete=self.athlete,
            cookies=self.client.session.get("switzerland_mobility_cookies"),
        )

        self.assertEqual(len(remote_routes), 82)

    @responses.activate
    def test_get_raw_route_details_success(self):
        route_id = 2191833
        route = SwitzerlandMobilityRoute(source_id=route_id, athlete=self.athlete)

        # intercept routes_list call to map.wanderland.ch with responses
        route_url = settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL % route_id

        route_details_json = read_data(file="2191833_show.json", dir_path=CURRENT_DIR)

        responses.add(
            responses.GET,
            route_url,
            content_type="application/json",
            body=route_details_json,
            status=200,
        )

        route.get_route_details(cookies=None)

        self.assertEqual("Haute Cime", route.name)
        self.assertIsInstance(route.geom, LineString)
        self.assertEqual(len(route.data.columns), 2)

    @responses.activate
    def test_get_raw_private_route_not_logged_in(self):
        route_id = 1
        route = SwitzerlandMobilityRouteFactory(source_id=route_id)

        # intercept routes_list call to map.wanderland.ch with responses
        route_url = settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL % route_id

        json_403 = read_data(file="403.json", dir_path=CURRENT_DIR)

        responses.add(
            responses.GET,
            route_url,
            content_type="application/json",
            body=json_403,
            status=403,
        )

        with self.assertRaises(SwitzerlandMobilityMissingCredentials):
            route.get_route_details(cookies=None)

    @responses.activate
    def test_get_raw_private_route_not_owner(self):
        route_id = 1
        route = SwitzerlandMobilityRouteFactory(source_id=route_id)

        # intercept routes_list call to map.wanderland.ch with responses
        route_url = settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL % route_id

        json_403 = read_data(file="403.json", dir_path=CURRENT_DIR)

        responses.add(
            responses.GET,
            route_url,
            content_type="application/json",
            body=json_403,
            status=403,
        )

        with self.assertRaises(SwitzerlandMobilityError):
            route.get_route_details(
                cookies=self.client.session["switzerland_mobility_cookies"]
            )

    @responses.activate
    def test_get_raw_route_details_404_error(self):
        route_id = 2
        route = SwitzerlandMobilityRoute(source_id=route_id)

        # intercept routes_list call to map.wanderland.ch with responses
        route_url = settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL % route_id

        json_404 = read_data(file="404.json", dir_path=CURRENT_DIR)

        responses.add(
            responses.GET,
            route_url,
            content_type="application/json",
            body=json_404,
            status=404,
        )

        with self.assertRaises(SwitzerlandMobilityError):
            route.get_route_details(cookies=None)

    def test_refresh_from_db_if_exists(self):
        route_stub = SwitzerlandMobilityRouteFactory.build()
        route_stub, exists = route_stub.refresh_from_db_if_exists()
        self.assertFalse(exists)

        saved_route = SwitzerlandMobilityRouteFactory(
            athlete=self.athlete,
            data_source="switzerland_mobility",
            source_id="123456",
        )
        saved_route, exists = saved_route.refresh_from_db_if_exists()
        self.assertTrue(exists)

        stub_like_saved_route = SwitzerlandMobilityRouteFactory.build(
            athlete=self.athlete,
            data_source="switzerland_mobility",
            source_id="123456",
        )
        (
            stub_like_saved_route,
            exists,
        ) = stub_like_saved_route.refresh_from_db_if_exists()
        self.assertTrue(exists)
        self.assertEqual(stub_like_saved_route, saved_route)

    #########
    # Views #
    #########

    @responses.activate
    def test_switzerland_mobility_display_route_deleted_data(self):
        route_id = 2191833
        route = SwitzerlandMobilityRouteFactory(
            source_id=route_id, athlete=self.athlete
        )

        # delete data file
        field = DataFrameField()
        file_path = field.storage.path(route.data.filepath)
        Path(file_path).unlink()

        details_url = settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL % route_id
        details_json = read_data("2191833_show.json", dir_path=CURRENT_DIR)

        responses.add(
            responses.GET,
            details_url,
            content_type="application/json",
            body=details_json,
            status=200,
        )

        url = reverse("routes:route", kwargs={"pk": route.id})
        response = self.client.get(url)

        assert response.status_code == 200

    @responses.activate
    def test_switzerland_mobility_display_route_deleted_data_not_owner(self):
        route_id = 2191833
        route = SwitzerlandMobilityRouteFactory(
            source_id=route_id, athlete=self.athlete
        )

        # delete data file
        field = DataFrameField()
        file_path = field.storage.path(route.data.filepath)
        Path(file_path).unlink()

        details_url = settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL % route_id
        details_json = read_data("403.json", dir_path=CURRENT_DIR)

        responses.add(
            responses.GET,
            details_url,
            content_type="application/json",
            body=details_json,
            status=403,
        )

        url = reverse("routes:route", kwargs={"pk": route.id})
        response = self.client.get(url)

        assert response.status_code == 404

    def test_importers_index_not_logged_redirected(self):
        self.client.logout()
        url = reverse("importers_index")
        redirect_url = "/login/?next=" + url
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_importers_index_view_logged_in(self):
        content = "Import routes"
        url = reverse("importers_index")
        response = self.client.get(url)
        self.assertContains(response, content)

    def test_switzerland_mobility_route_success(self):

        response = self.get_import_route_response(route_id=2823968)

        title = "<title>Home by Two - Import Haute Cime</title>"
        start_place_form_elements = [
            'name="start_place"',
            'class="field"',
            'id="id_start_place"',
        ]

        map_data = '<div id="main" class="leaflet-container-default"></div>'

        self.assertContains(response, title, html=True)
        for start_place_form_element in start_place_form_elements:
            self.assertContains(response, start_place_form_element)
        self.assertContains(response, map_data, html=True)

    def test_switzerland_mobility_route_with_no_switzerland_mobility_account_success(
        self,
    ):
        session = self.client.session
        del session["switzerland_mobility_cookies"]
        session.save()

        response = self.get_import_route_response(route_id=2823968)

        title = "<title>Home by Two - Import Haute Cime</title>"
        self.assertContains(response, title, html=True)

    def test_switzerland_mobility_route_redirect_to_login_with_route_id(self):
        session = self.client.session
        del session["switzerland_mobility_cookies"]
        session.save()

        source_id = 123456789
        response = self.get_import_route_response(
            route_id=source_id,
            response_file="403.json",
            status=403,
        )

        params = urlencode({"route_id": source_id})
        assert response.status_code == 302
        assert params in response.url

    def test_switzerland_mobility_route_already_imported(self):
        route_id = 2733343
        SwitzerlandMobilityRouteFactory(
            source_id=route_id,
            athlete=self.athlete,
        )

        content = "Already Imported"
        response = self.get_import_route_response(
            route_id=route_id, response_file="2733343_show.json"
        )

        self.assertContains(response, content)

    def test_switzerland_mobility_route_server_error(self):
        route_id = 999999999999
        response = self.get_import_route_response(
            route_id=route_id,
            response_file="500.html",
            status=500,
            content_type="text/html",
        )

        self.assertRedirects(response, reverse("routes:routes"))

    def test_switzerland_mobility_route_post_success_no_checkpoints(self):
        route_id = 2191833
        route = SwitzerlandMobilityRouteFactory.build(source_id=route_id)

        route.start_place.save()
        route.end_place.save()

        route_data = model_to_dict(route)
        post_data = {
            key: value
            for key, value in route_data.items()
            if key in RouteForm.Meta.fields
        }

        post_data.update(
            {
                "activity_type": 1,
                "start_place": route.start_place.id,
                "end_place": route.end_place.id,
            }
        )

        response = self.get_import_route_response(
            route_id=route_id,
            method="post",
            post_data=post_data,
        )

        route = SwitzerlandMobilityRoute.objects.get(source_id=route_id)
        redirect_url = reverse("routes:route", args=[route.id])

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_switzerland_mobility_route_post_success_with_checkpoints(self):
        # route to save
        route_id = 2191833
        route = SwitzerlandMobilityRouteFactory.build(
            source_id=route_id,
        )

        # save start and end place
        route.start_place.save()
        route.end_place.save()

        # checkpoints
        checkpoints_data = []
        number_of_checkpoints = 5

        for index in range(1, number_of_checkpoints + 1):
            line_location = index / (number_of_checkpoints + 1)
            place = PlaceFactory(
                geom=Point(
                    *route.geom.coords[int(route.geom.num_coords * line_location)],
                    srid=21781,
                )
            )
            checkpoints_data.append("_".join([str(place.id), str(line_location)]))

        route_data = model_to_dict(route)
        post_data = {
            key: value
            for key, value in route_data.items()
            if key in RouteForm.Meta.fields
        }

        post_data.update(
            {
                "activity_type": 1,
                "start_place": route.start_place.id,
                "end_place": route.end_place.id,
                "checkpoints": checkpoints_data,
            }
        )

        get_response = self.get_import_route_response(route_id=route_id)
        post_response = self.get_import_route_response(
            route_id=route_id,
            method="post",
            post_data=post_data,
        )

        checkpoint_choices = get_response.context["form"].fields["checkpoints"].choices

        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(len(checkpoint_choices), number_of_checkpoints)

        # a new route has been created with the post response
        route = SwitzerlandMobilityRoute.objects.get(source_id=route_id)
        checkpoints = Checkpoint.objects.filter(route=route.id)
        self.assertEqual(checkpoints.count(), number_of_checkpoints)

        # user is redirected
        redirect_url = reverse("routes:route", args=[route.id])
        self.assertRedirects(post_response, redirect_url)

    def test_switzerland_mobility_route_post_invalid_choice(self):
        route_id = 2191833
        route = SwitzerlandMobilityRouteFactory.build(source_id=route_id)

        route.start_place.save()
        route.end_place.save()

        route_data = model_to_dict(route)
        post_data = {
            key: value
            for key, value in route_data.items()
            if key in RouteForm.Meta.fields
        }

        post_data.update(
            {
                "start_place": route.start_place.id,
                "end_place": route.end_place.id,
                "checkpoints": [
                    "not_valid",
                    "invalid",
                    "0_valid",
                    "1_2",
                    "still_not_valid",
                ],
            }
        )

        del post_data["activity_type"]

        response = self.get_import_route_response(
            route_id=route_id,
            method="post",
            post_data=post_data,
        )

        alert_box = '<li class="box mrgv- alert error" >'
        required_field = "This field is required."
        invalid_value = "Invalid value"

        self.assertContains(response, alert_box)
        self.assertContains(response, required_field)
        self.assertContains(response, invalid_value)

    def test_switzerland_mobility_route_post_integrity_error(self):

        route_id = 2191833
        route = SwitzerlandMobilityRouteFactory(
            source_id=route_id, athlete=self.athlete
        )

        route_data = model_to_dict(route)
        post_data = {
            key: value
            for key, value in route_data.items()
            if key in RouteForm.Meta.fields
        }

        post_data["activity_type"] = 1

        response = self.get_import_route_response(
            route_id=route_id,
            method="post",
            post_data=post_data,
        )

        alert_box = '<li class="box mrgv- alert error" >'
        integrity_error = (
            "Integrity Error: duplicate key value violates unique constraint"
        )

        self.assertContains(response, alert_box)
        self.assertContains(response, integrity_error)

    @responses.activate
    def test_switzerland_mobility_routes_success(self):
        # deleted route
        SwitzerlandMobilityRouteFactory(athlete=self.athlete, source_id=123456)

        url = reverse("import_routes", kwargs={"data_source": "switzerland_mobility"})
        title_content = "Import Routes from Switzerland Mobility Plus"
        subsection_content = "<h2>Routes Deleted from Switzerland Mobility Plus</h2>"

        # intercept call to map.wanderland.ch
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        json_response = read_data(file="tracks_list.json", dir_path=CURRENT_DIR)

        responses.add(
            responses.GET,
            routes_list_url,
            content_type="application/json",
            body=json_response,
            status=200,
        )

        response = self.client.get(url)

        self.assertContains(response, title_content)
        self.assertContains(response, subsection_content, html=True)

    @responses.activate
    def test_switzerland_mobility_routes_error(self):
        url = reverse("import_routes", kwargs={"data_source": "switzerland_mobility"})

        # intercept call to map.wanderland.ch
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        json_response = "[]"

        responses.add(
            responses.GET,
            routes_list_url,
            content_type="application/json",
            body=json_response,
            status=500,
        )

        response = self.client.get(url, follow=False)
        redirected_response = self.client.get(url, follow=True)

        content = "Error 500: could not retrieve information from %s" % routes_list_url

        self.assertRedirects(response, reverse("routes:routes"))
        self.assertContains(redirected_response, content)

    def test_switzerland_mobility_routes_no_cookies(self):
        session = self.client.session
        del session["switzerland_mobility_cookies"]
        session.save()

        url = reverse("import_routes", kwargs={"data_source": "switzerland_mobility"})
        redirect_url = reverse("switzerland_mobility_login")
        response = self.client.get(url)
        assert response.status_code == 302
        assert response.url == redirect_url

        self.assertEqual(response.url, redirect_url)

    def test_switzerland_mobility_get_login_view(self):
        url = reverse("switzerland_mobility_login")
        content = '<form method="post">'
        response = self.client.get(url)

        self.assertContains(response, content)

    @responses.activate
    def test_switzerland_mobility_login_successful(self):
        json_response = '{"loginErrorMsg": "", "loginErrorCode": 200}'
        adding_headers = {"Set-Cookie": "mf-chmobil=123"}

        responses.add(
            responses.POST,
            settings.SWITZERLAND_MOBILITY_LOGIN_URL,
            content_type="application/json",
            body=json_response,
            status=200,
            adding_headers=adding_headers,
        )

        url = reverse("switzerland_mobility_login")
        data = {"username": "test_user", "password": "test_password"}
        response = self.client.post(url, data)

        mobility_cookies = self.client.session["switzerland_mobility_cookies"]
        redirect_url = resolve_url("import_routes", data_source="switzerland_mobility")

        assert response.status_code == 302
        assert response.url == redirect_url
        assert mobility_cookies["mf-chmobil"] == "123"

    @responses.activate
    def test_switzerland_mobility_login_successful_route_id(self):
        json_response = '{"loginErrorMsg": "", "loginErrorCode": 200}'
        adding_headers = {"Set-Cookie": "mf-chmobil=123"}

        responses.add(
            responses.POST,
            settings.SWITZERLAND_MOBILITY_LOGIN_URL,
            content_type="application/json",
            body=json_response,
            status=200,
            adding_headers=adding_headers,
        )
        source_id = 123456789
        url = reverse("switzerland_mobility_login")
        params = urlencode({"route_id": source_id})
        data = {"username": "test_user", "password": "test_password"}
        response = self.client.post(f"{url}?{params}", data)

        mobility_cookies = self.client.session["switzerland_mobility_cookies"]
        redirect_url = resolve_url(
            "import_route", data_source="switzerland_mobility", source_id=source_id
        )

        assert response.status_code == 302
        assert response.url == redirect_url
        assert mobility_cookies["mf-chmobil"] == "123"

    @responses.activate
    def test_switzerland_mobility_login_successful_route_id_bad(self):
        json_response = '{"loginErrorMsg": "", "loginErrorCode": 200}'
        adding_headers = {"Set-Cookie": "mf-chmobil=123"}

        responses.add(
            responses.POST,
            settings.SWITZERLAND_MOBILITY_LOGIN_URL,
            content_type="application/json",
            body=json_response,
            status=200,
            adding_headers=adding_headers,
        )

        url = reverse("switzerland_mobility_login")
        params = urlencode({"route_id": "bad_id"})
        data = {"username": "test_user", "password": "test_password"}
        response = self.client.post(f"{url}?{params}", data)

        mobility_cookies = self.client.session["switzerland_mobility_cookies"]
        redirect_url = resolve_url("import_routes", data_source="switzerland_mobility")

        assert response.status_code == 302
        assert response.url == redirect_url
        assert mobility_cookies["mf-chmobil"] == "123"

    @responses.activate
    def test_switzerland_mobility_login_failed(self):
        # remove switzerland mobility cookies
        session = self.client.session
        del session["switzerland_mobility_cookies"]
        session.save()

        url = reverse("switzerland_mobility_login")
        data = {"username": "test_user", "password": "test_password"}

        # intercept call to map.wanderland.ch with responses
        login_url = settings.SWITZERLAND_MOBILITY_LOGIN_URL
        # failed login response
        json_response = (
            '{"loginErrorMsg": "Incorrect login.", ' '"loginErrorCode": 500}'
        )

        responses.add(
            responses.POST,
            login_url,
            content_type="application/json",
            body=json_response,
            status=200,
        )
        response = self.client.post(url, data)

        self.assertContains(response, "Incorrect login.")
        assert "switzerland_mobility_cookies" not in self.client.session

    @responses.activate
    def test_switzerland_mobility_login_server_error(self):
        url = reverse("switzerland_mobility_login")
        data = {"username": "test_user", "password": "test_password"}
        content = "Error 500: logging to Switzerland Mobility."

        # intercept call to map.wanderland.ch with responses
        login_url = settings.SWITZERLAND_MOBILITY_LOGIN_URL
        responses.add(responses.POST, login_url, status=500)

        response = self.client.post(url, data)

        self.assertContains(response, content)

    def test_switzerland_mobility_login_method_not_allowed(self):
        url = reverse("switzerland_mobility_login")
        data = {"username": "test_user", "password": "test_password"}
        response = self.client.put(url, data)

        self.assertEqual(response.status_code, 405)

    #########
    # Forms #
    #########

    def test_switzerland_mobility_valid_login_form(self):
        username = "test@test.com"
        password = "123456"
        data = {"username": username, "password": password}
        form = SwitzerlandMobilityLogin(data=data)

        self.assertTrue(form.is_valid())

    def test_switzerland_mobility_invalid_login_form(self):
        username = ""
        password = ""
        data = {"username": username, "password": password}
        form = SwitzerlandMobilityLogin(data=data)

        self.assertFalse(form.is_valid())

    def test_switzerland_mobility_valid_route_form(self):
        route = SwitzerlandMobilityRouteFactory.build()
        route_data = model_to_dict(route)
        route_data.update(
            {
                "activity_type": 1,
                "start_place": route.start_place.id,
                "end_place": route.end_place.id,
            }
        )
        form = RouteForm(data=route_data)
        self.assertTrue(form.is_valid())

    def test_switzerland_mobility_invalid_route_form(self):
        route = SwitzerlandMobilityRouteFactory.build()
        route_data = model_to_dict(route)
        route_data.update(
            {"start_place": route.start_place.id, "end_place": route.end_place.id}
        )
        del route_data["activity_type"]
        form = RouteForm(data=route_data)
        self.assertFalse(form.is_valid())
