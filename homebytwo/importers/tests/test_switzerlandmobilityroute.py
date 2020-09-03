from json import loads as json_loads
from os.path import dirname, realpath
from re import compile as re_compile

from django.conf import settings
from django.contrib.gis.geos import LineString, Point
from django.forms.models import model_to_dict
from django.test import TestCase, override_settings
from django.urls import reverse

import httpretty
from requests.exceptions import ConnectionError

from ...routes.forms import RouteForm
from ...routes.models import Checkpoint
from ...routes.tests.factories import PlaceFactory
from ...utils.factories import AthleteFactory, UserFactory
from ...utils.tests import raise_connection_error, read_data
from ..exceptions import SwitzerlandMobilityError
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
        self.athlete = AthleteFactory(user__password="testpassword")
        self.client.login(username=self.athlete.user.username, password="testpassword")

        # add Switzerland Mobility cookies to the session
        session = self.client.session
        session["switzerland_mobility_cookies"] = {
            "mf-chmobil": "xxx",
            "srv": "yyy",
        }
        session.save()

    #########
    # Model #
    #########

    def test_request_json_success(self):
        cookies = self.client.session["switzerland_mobility_cookies"]

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
        cookies = self.client.session["switzerland_mobility_cookies"]

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
        cookies = self.client.session["switzerland_mobility_cookies"]
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
        remote_routes = manager.get_remote_routes_list(
            self.client.session, self.athlete
        )
        httpretty.disable()

        self.assertEqual(len(remote_routes), 82)

    def test_get_remote_routes_empty(self):
        # create user
        user = UserFactory()

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
        remote_routes = manager.get_remote_routes_list(self.client.session, user)
        httpretty.disable()

        self.assertEqual(len(remote_routes), 0)

    def test_get_remote_routes_list_server_error(self):
        # create user
        user = UserFactory()

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
            routes_manager.get_remote_routes_list(self.client.session, user)

        httpretty.disable()

    def test_get_remote_routes_list_connection_error(self):
        # create user
        athlete = self.athlete

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
            manager.get_remote_routes_list(self.client.session, athlete)

        httpretty.disable()

    def test_format_raw_remote_routes_success(self):
        raw_routes = json_loads(
            read_data(file="tracks_list.json", dir_path=CURRENT_DIR)
        )

        manager = SwitzerlandMobilityRoute.objects
        formatted_routes = manager._format_raw_remote_routes(raw_routes, self.athlete)

        self.assertTrue(type(formatted_routes) is list)
        self.assertEqual(len(formatted_routes), 82)
        for route in formatted_routes:
            self.assertIsInstance(route, SwitzerlandMobilityRoute)
            self.assertEqual(route.description, "")

    def test_format_raw_remote_routes_empty(self):
        raw_routes = []

        routes_manager = SwitzerlandMobilityRoute.objects
        formatted_routes = routes_manager._format_raw_remote_routes(
            raw_routes, self.athlete,
        )

        self.assertEqual(len(formatted_routes), 0)
        self.assertTrue(type(formatted_routes) is list)

    def test_check_for_existing_routes_success(self):

        # save an existing route
        SwitzerlandMobilityRouteFactory(
            source_id=2191833, name="Haute Cime", athlete=self.athlete,
        )

        # save a route not on the remote
        SwitzerlandMobilityRouteFactory(source_id=1234567, athlete=self.athlete)

        remote_routes = [
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

        local_routes = SwitzerlandMobilityRoute.objects.for_user(self.athlete.user)
        new_routes, existing_routes, deleted_routes = split_routes(
            remote_routes, local_routes
        )

        self.assertEqual(len(new_routes), 3)
        self.assertEqual(len(existing_routes), 1)
        self.assertEqual(len(deleted_routes), 1)

    def test_get_remote_routes_list_success(self):

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

        remote_routes = SwitzerlandMobilityRoute.objects.get_remote_routes_list(
            self.client.session, self.athlete
        )
        httpretty.disable()

        self.assertEqual(len(remote_routes), 82)

    def test_get_raw_route_details_success(self):
        route_id = 2191833
        route = SwitzerlandMobilityRoute(source_id=route_id, athlete=self.athlete)

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
        self.assertIsInstance(route.geom, LineString)
        self.assertEqual(len(route.data.columns), 2)

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
        (
            stub_like_saved_route,
            exists,
        ) = stub_like_saved_route.refresh_from_db_if_exists()
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
        url = reverse(
            "import_route",
            kwargs={"data_source": "switzerland_mobility", "source_id": route_id},
        )

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

        route_id = 2823968
        url = reverse(
            "import_route",
            kwargs={"data_source": "switzerland_mobility", "source_id": route_id},
        )

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
        self.assertContains(response, title, html=True)

    def test_switzerland_mobility_route_already_imported(self):
        route_id = 2733343
        SwitzerlandMobilityRouteFactory(
            source_id=route_id, athlete=self.athlete,
        )

        url = reverse(
            "import_route",
            kwargs={"data_source": "switzerland_mobility", "source_id": route_id},
        )
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
        url = reverse(
            "import_route",
            kwargs={"data_source": "switzerland_mobility", "source_id": route_id},
        )

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

        url = reverse(
            "import_route",
            kwargs={"data_source": "switzerland_mobility", "source_id": route_id},
        )

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

        response = self.client.post(url, post_data)

        httpretty.disable()

        route = SwitzerlandMobilityRoute.objects.get(source_id=route_id)
        redirect_url = reverse("routes:route", args=[route.id])

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_switzerland_mobility_route_post_success_with_checkpoints(self):
        # route to save
        route_id = 2191833
        route = SwitzerlandMobilityRouteFactory.build(source_id=route_id,)

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
                    srid=21781
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

        import_url = reverse(
            "import_route",
            kwargs={"data_source": "switzerland_mobility", "source_id": route_id},
        )

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

        get_response = self.client.post(import_url)
        post_response = self.client.post(import_url, post_data)

        httpretty.disable()

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
        url = reverse(
            "import_route",
            kwargs={"data_source": "switzerland_mobility", "source_id": route_id},
        )

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

        response = self.client.post(url, post_data)

        httpretty.disable()

        alert_box = '<li class="box mrgv- alert error">'
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
        url = reverse(
            "import_route",
            kwargs={"data_source": "switzerland_mobility", "source_id": route_id},
        )

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

        response = self.client.post(url, post_data)

        httpretty.disable()

        alert_box = '<li class="box mrgv- alert error">'
        integrity_error = (
            "Integrity Error: duplicate key value violates unique constraint"
        )

        self.assertContains(response, alert_box)
        self.assertContains(response, integrity_error)

    def test_switzerland_mobility_routes_success(self):
        # deleted route
        SwitzerlandMobilityRouteFactory(athlete=self.athlete, source_id=123456)

        url = reverse("import_routes", kwargs={"data_source": "switzerland_mobility"})
        title_content = "Import Routes from Switzerland Mobility Plus"
        subsection_content = "<h2>Routes Deleted from Switzerland Mobility Plus</h2>"

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

        self.assertContains(response, title_content)
        self.assertContains(response, subsection_content, html=True)

    def test_switzerland_mobility_routes_error(self):
        url = reverse("import_routes", kwargs={"data_source": "switzerland_mobility"})

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

        response = self.client.get(url, follow=False)
        redirected_response = self.client.get(url, follow=True)

        httpretty.disable()

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
        adding_headers = {"Set-Cookie": "mf-chmobil=123"}

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
        self.assertEqual(
            response.url,
            reverse("import_routes", kwargs={"data_source": "switzerland_mobility"}),
        )
        self.assertEqual(mobility_cookies["mf-chmobil"], "123")

    def test_switzerland_mobility_login_failed(self):
        # remove switzerland mobiility cookies
        session = self.client.session
        del session["switzerland_mobility_cookies"]
        session.save()

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

    def test_switzerland_mobility_login_method_not_allowed(self):
        url = reverse("switzerland_mobility_login")
        data = {"username": "testuser", "password": "testpassword"}
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
