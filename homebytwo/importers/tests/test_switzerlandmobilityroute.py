from json import loads as json_loads
from os.path import dirname, realpath
from re import compile as re_compile

from django.conf import settings
from django.forms.models import model_to_dict
from django.test import TestCase, override_settings
from django.urls import reverse

import httpretty
from requests.exceptions import ConnectionError

from ...routes.models import Checkpoint
from ...utils.factories import AthleteFactory, UserFactory
from ...utils.tests import raise_connection_error, read_data
from ..forms import ImportersRouteForm, SwitzerlandMobilityLogin
from ..models import SwitzerlandMobilityRoute
from ..models.switzerlandmobilityroute import request_json
from ..utils import SwitzerlandMobilityError, split_in_new_and_existing_routes
from .factories import SwitzerlandMobilityRouteFactory

CURRENT_DIR = dirname(realpath(__file__))


@override_settings(
    SWITZERLAND_MOBILITY_LOGIN_URL="https://example.com/login",
    SWITZERLAND_MOBILITY_LIST_URL="https://example.com/tracks",
    SWITZERLAND_MOBILITY_META_URL="https://example.com/track/%d/getmeta",
    SWITZERLAND_MOBILITY_ROUTE_DATA_URL="https://example.com/track/%d/show",
)
class SwitzerlandMobility(TestCase):
    """
    Test the Switzerland Mobility route importer
    """

    def add_cookies_to_session(self):
        cookies = {"mf-chmobil": "xxx", "srv": "yyy"}
        session = self.client.session
        session["switzerland_mobility_cookies"] = cookies
        session.save()
        return session

    def setUp(self):
        # Add user to the test database and log him in
        self.athlete = AthleteFactory(user__password="testpassword")
        self.client.login(username=self.athlete.user.username, password="testpassword")

    #########
    # Model #
    #########

    def test_request_json_success(self):
        # save cookies to session
        session = self.add_cookies_to_session()
        cookies = session["switzerland_mobility_cookies"]

        url = "https://testurl.ch"

        # intercept call with httpretty
        body = '[123456, "Test", null]'

        httpretty.enable(allow_net_connect=False)

        httpretty.register_uri(
            httpretty.GET, url, content_type="application/json", body=body, status=200
        )

        json_response = request_json(url, cookies)

        httpretty.disable()

        self.assertEqual(json_loads(body), json_response)

    def test_request_json_server_error(self):
        # save cookies to session
        session = self.add_cookies_to_session()
        cookies = session["switzerland_mobility_cookies"]

        url = "https://testurl.ch"

        # intercept call with httpretty
        html_response = read_data(file="500.html", dir_path=CURRENT_DIR)

        httpretty.enable(allow_net_connect=False)

        httpretty.register_uri(
            httpretty.GET, url, content_type="text/html", body=html_response, status=500
        )
        with self.assertRaises(SwitzerlandMobilityError):
            request_json(url, cookies)

        httpretty.disable()

    def test_request_json_connection_error(self):
        # save cookies to session
        session = self.add_cookies_to_session()
        cookies = session["switzerland_mobility_cookies"]
        url = "https://testurl.ch"

        # intercept call with httpretty
        httpretty.enable(allow_net_connect=False)

        httpretty.register_uri(
            httpretty.GET, url, body=raise_connection_error,
        )
        with self.assertRaises(ConnectionError):
            request_json(url, cookies)

        httpretty.disable()

    def test_get_remote_raw_routes_success(self):
        # save cookies to session
        session = self.add_cookies_to_session()

        # intercept call to map.wandland.ch with httpretty
        httpretty.enable(allow_net_connect=False)
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        json_response = read_data("tracks_list.json", dir_path=CURRENT_DIR)

        httpretty.register_uri(
            httpretty.GET,
            routes_list_url,
            content_type="application/json",
            body=json_response,
            status=200,
        )
        manager = SwitzerlandMobilityRoute.objects
        new_routes, old_routes = manager.get_remote_routes(session, self.athlete)
        httpretty.disable()

        self.assertEqual(len(new_routes + old_routes), 37)

    def test_get_remote_routes_empty(self):
        # create user
        user = UserFactory()

        # save cookies to session
        session = self.add_cookies_to_session()

        # intercept call to map.wandland.ch with httpretty
        httpretty.enable(allow_net_connect=False)
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        json_response = "[]"

        httpretty.register_uri(
            httpretty.GET,
            routes_list_url,
            content_type="application/json",
            body=json_response,
            status=200,
        )
        manager = SwitzerlandMobilityRoute.objects
        new_routes, old_routes = manager.get_remote_routes(session, user)
        httpretty.disable()

        self.assertEqual(len(new_routes + old_routes), 0)

    def test_get_remote_routes_server_error(self):
        # create user
        user = UserFactory()

        # save cookies to session
        session = self.add_cookies_to_session()

        # intercept call to map.wandland.ch with httpretty
        httpretty.enable(allow_net_connect=False)
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        json_response = "[]"

        httpretty.register_uri(
            httpretty.GET,
            routes_list_url,
            content_type="application/json",
            body=json_response,
            status=500,
        )

        routes_manager = SwitzerlandMobilityRoute.objects
        with self.assertRaises(SwitzerlandMobilityError):
            routes_manager.get_remote_routes(session, user)

        httpretty.disable()

    def test_get_remote_routes_connection_error(self):
        # create user
        athlete = self.athlete

        # save cookies to session
        session = self.add_cookies_to_session()

        # intercept call to map.wandland.ch with httpretty
        httpretty.enable(allow_net_connect=False)
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL

        httpretty.register_uri(
            httpretty.GET,
            routes_list_url,
            content_type="application/json",
            body=raise_connection_error,
        )

        manager = SwitzerlandMobilityRoute.objects
        with self.assertRaises(ConnectionError):
            manager.get_remote_routes(session, athlete)

        httpretty.disable()

    def test_format_raw_remote_routes_success(self):
        raw_routes = json_loads(
            read_data(file="tracks_list.json", dir_path=CURRENT_DIR)
        )

        manager = SwitzerlandMobilityRoute.objects
        formatted_routes = manager.format_raw_remote_routes(raw_routes, self.athlete,)

        self.assertTrue(type(formatted_routes) is list)
        self.assertEqual(len(formatted_routes), 37)
        for route in formatted_routes:
            self.assertTrue(isinstance(route, SwitzerlandMobilityRoute))
            self.assertEqual(route.description, "")

    def test_format_raw_remote_routes_empty(self):
        raw_routes = []

        routes_manager = SwitzerlandMobilityRoute.objects
        formatted_routes = routes_manager.format_raw_remote_routes(
            raw_routes, self.athlete,
        )

        self.assertEqual(len(formatted_routes), 0)
        self.assertTrue(type(formatted_routes) is list)

    def test_add_route_meta_success(self):
        route = SwitzerlandMobilityRoute(source_id=2191833)
        meta_url = settings.SWITZERLAND_MOBILITY_META_URL % route.source_id

        # Turn the route meta URL into a regular expression
        meta_url = re_compile(meta_url.replace(str(route.source_id), r"(\d+)"))

        httpretty.enable(allow_net_connect=False)

        route_json = read_data("track_info.json", dir_path=CURRENT_DIR)

        httpretty.register_uri(
            httpretty.GET,
            meta_url,
            content_type="application/json",
            body=route_json,
            status=200,
        )

        route.add_route_remote_meta()

        self.assertEqual(route.totalup.m, 1234.5)

    def test_check_for_existing_routes_success(self):

        # save an existing route
        SwitzerlandMobilityRouteFactory(
            source_id=2191833, name="Haute Cime", athlete=self.athlete,
        )

        formatted_routes = [
            SwitzerlandMobilityRouteFactory.build(
                name="Haute Cime", athlete=self.athlete, source_id=2191833,
            ),
            SwitzerlandMobilityRouteFactory.build(
                name="Grammont", athlete=self.athlete, source_id=2433141,
            ),
            SwitzerlandMobilityRouteFactory.build(
                name="Rochers de Nayes", athlete=self.athlete, source_id=2692136,
            ),
            SwitzerlandMobilityRouteFactory.build(
                name="Villeneuve - Leysin", athlete=self.athlete, source_id=3011765,
            ),
        ]

        (new_routes, old_routes,) = split_in_new_and_existing_routes(
            routes=formatted_routes,
        )

        self.assertEqual(len(new_routes), 3)
        self.assertEqual(len(old_routes), 1)

    def test_get_remote_routes_success(self):
        # save cookies to session
        session = self.add_cookies_to_session()

        # save an existing route
        SwitzerlandMobilityRouteFactory(athlete=self.athlete)

        # intercept routes_list call to map.wandland.ch with httpretty
        httpretty.enable(allow_net_connect=False)
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        json_response = read_data("tracks_list.json", dir_path=CURRENT_DIR)

        httpretty.register_uri(
            httpretty.GET,
            routes_list_url,
            content_type="application/json",
            body=json_response,
            status=200,
        )

        # intercept getmeta call to map.wandland.ch with httpretty
        # remove "https://
        route_meta_url = settings.SWITZERLAND_MOBILITY_META_URL[8:]
        # Turn the route meta URL into a regular expression
        route_meta_url = re_compile(route_meta_url.replace("%d", r"(\w+)"))

        route_json = read_data("track_info.json", dir_path=CURRENT_DIR)

        httpretty.register_uri(
            httpretty.GET,
            route_meta_url,
            content_type="application/json",
            body=route_json,
            status=200,
        )

        new_routes, old_routes = SwitzerlandMobilityRoute.objects.get_remote_routes(
            session, self.athlete
        )
        httpretty.disable()

        self.assertEqual(len(new_routes), 36)
        self.assertEqual(len(old_routes), 1)

    def test_get_raw_route_details_success(self):
        route_id = 2191833
        route = SwitzerlandMobilityRoute(source_id=route_id)

        # intercept routes_list call to map.wandland.ch with httpretty
        httpretty.enable(allow_net_connect=False)
        route_url = settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL % route_id

        route_details_json = read_data(file="2191833_show.json", dir_path=CURRENT_DIR)

        httpretty.register_uri(
            httpretty.GET,
            route_url,
            content_type="application/json",
            body=route_details_json,
            status=200,
        )

        route.get_route_details()

        httpretty.disable()

        self.assertEqual("Haute Cime", route.name)
        self.assertEqual(28517.8, route.length)

    def test_get_raw_route_details_error(self):
        route_id = 999999999
        route = SwitzerlandMobilityRoute(source_id=route_id)

        # intercept routes_list call to map.wandland.ch with httpretty
        httpretty.enable(allow_net_connect=False)
        route_url = settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL % route_id

        html_response = read_data(file="404.html", dir_path=CURRENT_DIR)

        httpretty.register_uri(
            httpretty.GET,
            route_url,
            content_type="text/html",
            body=html_response,
            status=404,
        )

        with self.assertRaises(SwitzerlandMobilityError):
            route.get_route_details()

        httpretty.disable()

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
        stub_like_saved_route, exists = stub_like_saved_route.refresh_from_db_if_exists()
        self.assertTrue(exists)
        self.assertEqual(stub_like_saved_route, saved_route)

    #########
    # Views #
    #########

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
        route_id = 2823968
        url = reverse("switzerland_mobility_route", args=[route_id])

        # intercept call to Switzerland Mobility with httpretty
        httpretty.enable(allow_net_connect=False)
        details_json_url = settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL % route_id
        json_response = read_data(file="2191833_show.json", dir_path=CURRENT_DIR)

        httpretty.register_uri(
            httpretty.GET,
            details_json_url,
            content_type="application/json",
            body=json_response,
            status=200,
        )

        response = self.client.get(url)

        httpretty.disable()

        title = "<title>Home by Two - Import Haute Cime</title>"
        start_place_form_elements = [
            'name="route-start_place"',
            'class="field"',
            'id="id_route-start_place"',
        ]
        places_formset = (
            '<input type="hidden" name="places-TOTAL_FORMS" '
            'value="0" id="id_places-TOTAL_FORMS">'
        )

        map_data = '<div id="main" class="leaflet-container-default"></div>'

        self.assertContains(response, title, html=True)
        for start_place_form_element in start_place_form_elements:
            self.assertContains(response, start_place_form_element)
        self.assertContains(response, places_formset, html=True)
        self.assertContains(response, map_data, html=True)

    def test_switzerland_mobility_route_already_imported(self):
        route_id = 2733343
        SwitzerlandMobilityRouteFactory(
            source_id=route_id, athlete=self.athlete,
        )

        url = reverse("switzerland_mobility_route", args=[route_id])
        content = "Already Imported"

        # intercept call to Switzerland Mobility with httpretty
        httpretty.enable(allow_net_connect=False)
        details_json_url = settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL % route_id
        json_response = read_data(file="2733343_show.json", dir_path=CURRENT_DIR)

        httpretty.register_uri(
            httpretty.GET,
            details_json_url,
            content_type="application/json",
            body=json_response,
            status=200,
        )

        response = self.client.get(url)

        httpretty.disable()

        self.assertContains(response, content)

    def test_switzerland_mobility_route_server_error(self):
        route_id = 999999999999
        url = reverse("switzerland_mobility_route", args=[route_id])
        content = "Error 500"

        # intercept call to Switzerland Mobility with httpretty
        httpretty.enable(allow_net_connect=False)
        details_json_url = settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL % route_id
        html_response = read_data(file="500.html", dir_path=CURRENT_DIR)

        httpretty.register_uri(
            httpretty.GET,
            details_json_url,
            content_type="text/html",
            body=html_response,
            status=500,
        )

        response = self.client.get(url)
        httpretty.disable()

        self.assertContains(response, content)

    def test_switzerland_mobility_route_post_success_no_places(self):
        route_id = 2191833
        route = SwitzerlandMobilityRouteFactory.build(source_id=route_id)

        start_place = route.start_place
        start_place.save()
        end_place = route.end_place
        end_place.save()

        route_data = model_to_dict(route)
        post_data = {"route-" + key: value for key, value in route_data.items()}
        del post_data["route-image"]

        post_data.update(
            {
                "route-activity_type": 1,
                "route-start_place": start_place.id,
                "route-end_place": end_place.id,
                "route-geom": route.geom.wkt,
                "route-data": route.data.to_json(orient="records"),
                "places-TOTAL_FORMS": 0,
                "places-INITIAL_FORMS": 0,
                "places-MIN_NUM_FORMS": 0,
                "places-MAX_NUM_FORMS": 1000,
            }
        )

        url = reverse("switzerland_mobility_route", args=[route_id])
        response = self.client.post(url, post_data)

        route = SwitzerlandMobilityRoute.objects.get(source_id=route_id)
        redirect_url = reverse("routes:route", args=[route.id])

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_switzerland_mobility_route_post_success_place(self):
        route_id = 2191833
        route = SwitzerlandMobilityRouteFactory.build(source_id=route_id)

        start_place = route.start_place
        start_place.save()
        end_place = route.end_place
        end_place.save()

        route_data = model_to_dict(route)
        post_data = {"route-" + key: value for key, value in route_data.items()}
        del post_data["route-image"]

        post_data.update(
            {
                "route-activity_type": 1,
                "route-start_place": start_place.id,
                "route-end_place": end_place.id,
                "route-geom": route.geom.wkt,
                "route-data": route.data.to_json(orient="records"),
                "places-TOTAL_FORMS": 2,
                "places-INITIAL_FORMS": 0,
                "places-MIN_NUM_FORMS": 0,
                "places-MAX_NUM_FORMS": 1000,
                "places-0-place": start_place.id,
                "places-0-line_location": 0.0207291870756597,
                "places-0-altitude_on_route": 123,
                "places-0-id": "",
                "places-0-include": True,
                "places-1-place": end_place.id,
                "places-1-line_location": 0.039107325861928,
                "places-1-altitude_on_route": 123,
                "places-1-id": "",
                "places-1-include": True,
            }
        )

        url = reverse("switzerland_mobility_route", args=[route_id])
        response = self.client.post(url, post_data)

        # a new route has been created
        route = SwitzerlandMobilityRoute.objects.get(source_id=route_id)
        route_places = Checkpoint.objects.filter(route=route.id)
        self.assertEqual(route_places.count(), 2)

        redirect_url = reverse("routes:route", args=[route.id])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_switzerland_mobility_route_post_no_validation_places(self):
        route_id = 2191833
        route = SwitzerlandMobilityRouteFactory.build(source_id=route_id)

        start_place = route.start_place
        start_place.save()
        end_place = route.end_place
        end_place.save()

        route_data = model_to_dict(route)
        post_data = {"route-" + key: value for key, value in route_data.items()}
        del post_data["route-image"]

        post_data.update(
            {
                "route-activity_type": 1,
                "route-start_place": start_place.id,
                "route-end_place": end_place.id,
                "route-geom": route.geom.wkt,
                "route-data": route.data.to_json(orient="records"),
                "places-TOTAL_FORMS": 2,
                "places-INITIAL_FORMS": 0,
                "places-MIN_NUM_FORMS": 0,
                "places-MAX_NUM_FORMS": 1000,
                "places-0-place": start_place.id,
                "places-0-altitude_on_route": "not a number",
                "places-0-id": "",
                "places-1-place": end_place.id,
                "places-1-line_location": 0.039107325861928,
                "places-1-altitude_on_route": 123,
                "places-1-id": "",
            }
        )

        url = reverse("switzerland_mobility_route", args=[route_id])
        response = self.client.post(url, post_data)

        alert_box = '<li class="box mrgv- alert error">'
        required_field = "This field is required."
        not_a_number = "Enter a number."

        self.assertContains(response, alert_box)
        self.assertContains(response, required_field)
        self.assertContains(response, not_a_number)

    def test_switzerland_mobility_route_post_integrity_error(self):
        route_id = 2191833
        route = SwitzerlandMobilityRouteFactory(
            source_id=route_id, athlete=self.athlete
        )

        start_place = route.start_place
        end_place = route.end_place

        route_data = model_to_dict(route)
        post_data = {"route-" + key: value for key, value in route_data.items()}

        del post_data["route-image"]

        post_data.update(
            {
                "route-start_place": start_place.id,
                "route-end_place": end_place.id,
                "route-geom": route.geom.wkt,
                "route-data": route.data.to_json(orient="records"),
                "places-TOTAL_FORMS": 2,
                "places-INITIAL_FORMS": 0,
                "places-MIN_NUM_FORMS": 0,
                "places-MAX_NUM_FORMS": 1000,
                "places-0-place": start_place.id,
                "places-0-line_location": 0.0207291870756597,
                "places-0-altitude_on_route": 123,
                "places-0-id": "",
                "places-1-place": end_place.id,
                "places-1-line_location": 0.039107325861928,
                "places-1-altitude_on_route": 123,
                "places-1-id": "",
            }
        )

        url = reverse("switzerland_mobility_route", args=[route_id])
        response = self.client.post(url, post_data)

        alert_box = '<li class="box mrgv- alert error">'
        integrity_error = (
            "Integrity Error: duplicate key value violates unique constraint"
        )

        self.assertContains(response, alert_box)
        self.assertContains(response, integrity_error)

    def test_switzerland_mobility_routes_success(self):
        url = reverse("switzerland_mobility_routes")
        content = "Import Routes from Switzerland Mobility Plus"
        self.add_cookies_to_session()

        # intercept call to map.wanderland.ch
        httpretty.enable(allow_net_connect=False)
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        json_response = read_data(file="tracks_list.json", dir_path=CURRENT_DIR)

        httpretty.register_uri(
            httpretty.GET,
            routes_list_url,
            content_type="application/json",
            body=json_response,
            status=200,
        )

        response = self.client.get(url)

        httpretty.disable()

        self.assertContains(response, content)

    def test_switzerland_mobility_routes_error(self):
        url = reverse("switzerland_mobility_routes")
        self.add_cookies_to_session()

        # intercept call to map.wanderland.ch
        httpretty.enable(allow_net_connect=False)
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        json_response = "[]"

        httpretty.register_uri(
            httpretty.GET,
            routes_list_url,
            content_type="application/json",
            body=json_response,
            status=500,
        )

        response = self.client.get(url)

        httpretty.disable()

        content = "Error 500: could not retrieve information from %s" % routes_list_url

        self.assertContains(response, content)

    def test_switzerland_mobility_routes_no_cookies(self):
        url = reverse("switzerland_mobility_routes")
        redirect_url = reverse("switzerland_mobility_login")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_switzerland_mobility_get_login_view(self):
        url = reverse("switzerland_mobility_login")
        content = 'action="%s"' % url
        response = self.client.get(url)

        self.assertContains(response, content)

    def test_switzerland_mobility_login_successful(self):
        url = reverse("switzerland_mobility_login")
        data = {"username": "testuser", "password": "testpassword"}

        # intercept call to map.wandland.ch with httpretty
        httpretty.enable(allow_net_connect=False)
        login_url = settings.SWITZERLAND_MOBILITY_LOGIN_URL
        # successful login response
        json_response = '{"loginErrorMsg": "", "loginErrorCode": 200}'
        adding_headers = {"Set-Cookie": "mf-chmobil=xxx"}

        httpretty.register_uri(
            httpretty.POST,
            login_url,
            content_type="application/json",
            body=json_response,
            status=200,
            adding_headers=adding_headers,
        )
        response = self.client.post(url, data)
        httpretty.disable()

        mobility_cookies = self.client.session["switzerland_mobility_cookies"]

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("switzerland_mobility_routes"))
        self.assertEqual(mobility_cookies["mf-chmobil"], "xxx")

    def test_switzerland_mobility_login_failed(self):
        url = reverse("switzerland_mobility_login")
        data = {"username": "testuser", "password": "testpassword"}

        # intercept call to map.wandland.ch with httpretty
        httpretty.enable(allow_net_connect=False)
        login_url = settings.SWITZERLAND_MOBILITY_LOGIN_URL
        # failed login response
        json_response = (
            '{"loginErrorMsg": "Incorrect login.", ' '"loginErrorCode": 500}'
        )

        httpretty.register_uri(
            httpretty.POST,
            login_url,
            content_type="application/json",
            body=json_response,
            status=200,
        )
        response = self.client.post(url, data)
        httpretty.disable()

        self.assertContains(response, "Incorrect login.")
        with self.assertRaises(KeyError):
            self.client.session["switzerland_mobility_cookies"]

    def test_switzerland_mobility_login_server_error(self):
        url = reverse("switzerland_mobility_login")
        data = {"username": "testuser", "password": "testpassword"}
        content = "Error 500: logging to Switzeland Mobility."

        # intercept call to map.wandland.ch with httpretty
        httpretty.enable(allow_net_connect=False)
        login_url = settings.SWITZERLAND_MOBILITY_LOGIN_URL
        httpretty.register_uri(httpretty.POST, login_url, status=500)

        response = self.client.post(url, data)
        httpretty.disable()

        self.assertContains(response, content)

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

    def test_switzerland_mobility_valid_model_form(self):
        route = SwitzerlandMobilityRouteFactory.build()
        route_data = model_to_dict(route)
        route_data.update(
            {
                "activity_type": 1,
                "geom": route.geom.wkt,
                "data": route.data.to_json(orient="records"),
                "start_place": route.start_place.id,
                "end_place": route.end_place.id,
            }
        )
        form = ImportersRouteForm(data=route_data)
        self.assertTrue(form.is_valid())

    def test_switzerland_mobility_invalid_model_form(self):
        route = SwitzerlandMobilityRouteFactory.build()
        route_data = model_to_dict(route)
        route_data.update(
            {
                "geom": route.geom.wkt,
                "start_place": route.start_place.id,
                "end_place": route.end_place.id,
            }
        )
        del route_data["geom"]
        form = ImportersRouteForm(data=route_data)
        self.assertFalse(form.is_valid())
