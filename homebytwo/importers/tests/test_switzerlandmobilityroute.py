from functools import partial
from json import loads as json_loads
from os.path import dirname, realpath
from pathlib import Path
from re import compile as re_compile

import pytest
from django.conf import settings
from django.contrib.gis.geos import LineString, Point
from django.forms.models import model_to_dict
from django.shortcuts import resolve_url
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.http import urlencode

import responses
from pytest_django.asserts import assertContains, assertRedirects
from requests.exceptions import ConnectionError

from ...routes.fields import DataFrameField
from ...routes.forms import RouteForm
from ...routes.models import Checkpoint
from ...routes.tests.factories import PlaceFactory
from ...utils.factories import AthleteFactory, UserFactory
from ...utils.tests import create_checkpoints_from_geom, get_route_post_data, read_data
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
        follow=False,
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
            return self.client.get(url, follow=follow)
        if method == "post":
            return self.client.post(url, post_data, follow=follow)

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

    def test_switzerland_mobility_get_or_stub_new(self):
        source_id = 123456789
        route, update = SwitzerlandMobilityRoute.get_or_stub(
            source_id=source_id, athlete=self.athlete
        )

        assert route.data_source == "switzerland_mobility"
        assert route.source_id == source_id
        assert route.athlete == self.athlete
        assert not update
        assert not route.pk

    def test_switzerland_mobility_get_or_stub_existing(self):
        existing_route = SwitzerlandMobilityRouteFactory(athlete=self.athlete)
        retrieved_route, update = SwitzerlandMobilityRoute.get_or_stub(
            source_id=existing_route.source_id, athlete=self.athlete
        )

        assert retrieved_route.data_source == "switzerland_mobility"
        assert retrieved_route.source_id == existing_route.source_id
        assert retrieved_route.athlete == self.athlete
        assert update
        assert retrieved_route.pk

    #########
    # Views #
    #########

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

    def test_get_import_switzerland_mobility_route(self):

        possible_checkpoint_place = PlaceFactory(
            geom=Point(x=770627.7496480079, y=5804675.451271648)
        )
        response = self.get_import_route_response(route_id=2823968)

        title = "<title>Home by Two - Import Haute Cime</title>"
        start_place_form_elements = [
            'name="start_place"',
            'class="field"',
            'id="id_start_place"',
        ]
        map_data = '<div id="mapid"></div>'

        self.assertContains(response, title, html=True)
        self.assertContains(response, possible_checkpoint_place.name)
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

    def test_switzerland_mobility_route_already_imported(self):
        route_id = 2733343
        SwitzerlandMobilityRouteFactory(
            source_id=route_id,
            athlete=self.athlete,
        )

        response = self.get_import_route_response(
            route_id=route_id, response_file="2733343_show.json"
        )

        content = "Update"
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


@pytest.fixture
def mock_login_response(mocked_responses, settings):
    settings.SWITZERLAND_MOBILITY_LOGIN_URL = "https://example.com/login"
    json_response = '{"loginErrorMsg": "", "loginErrorCode": 200}'
    adding_headers = {"Set-Cookie": "mf-chmobil=123"}

    def _mock_login_response():
        mocked_responses.add(
            responses.POST,
            settings.SWITZERLAND_MOBILITY_LOGIN_URL,
            body=json_response,
            adding_headers=adding_headers,
            content_type="application/json",
            status=200,
        )

    return _mock_login_response


@pytest.fixture
def mock_failed_login_response(mocked_responses, settings):
    settings.SWITZERLAND_MOBILITY_LOGIN_URL = "https://example.com/login"
    json_response = '{"loginErrorMsg": "Incorrect login.", ' '"loginErrorCode": 500}'

    def _mock_failed_login_response():
        mocked_responses.add(
            responses.POST,
            settings.SWITZERLAND_MOBILITY_LOGIN_URL,
            content_type="application/json",
            body=json_response,
            status=200,
        )

    return _mock_failed_login_response


@pytest.fixture
def mock_sm_routes_response(mock_routes_response, settings):
    settings.SWITZERLAND_MOBILITY_LIST_URL = (
        settings.SWITZERLAND_MOBILITY_LIST_URL or "https://example.com/tracks"
    )
    return partial(mock_routes_response, data_source="switzerland_mobility")


@pytest.fixture
def mock_sm_route_response(mock_route_details_response):
    return partial(mock_route_details_response, "switzerland_mobility")


###################################
# view switzerland_mobility_login #
###################################


def test_get_switzerland_mobility_login(athlete, client):
    url = reverse("switzerland_mobility_login")
    form_content = '<form method="post">'
    text_content = "We do not store your Switzerland Mobility log-in details."
    response = client.get(url)

    assertContains(response, form_content)
    assertContains(response, text_content)


def test_post_switzerland_mobility_login(
    athlete, client, mock_login_response, mock_sm_routes_response
):

    url = reverse("switzerland_mobility_login")
    data = {"username": "test_user", "password": "test_password"}
    mock_login_response()
    mock_sm_routes_response(athlete=athlete)
    response = client.post(url, data)

    mobility_cookies = client.session["switzerland_mobility_cookies"]
    redirect_url = resolve_url("import_routes", data_source="switzerland_mobility")

    assertRedirects(response, redirect_url)
    assert mobility_cookies["mf-chmobil"] == "123"


def test_post_switzerland_mobility_login_import_id(
    athlete, client, mock_login_response, mock_sm_route_response
):
    source_id = 1234567
    url = reverse("switzerland_mobility_login")
    params = urlencode({"import": source_id})
    data = {"username": athlete.user.username, "password": "test_password"}
    mock_login_response()
    mock_sm_route_response(source_id=source_id)
    response = client.post(f"{url}?{params}", data)

    mobility_cookies = client.session["switzerland_mobility_cookies"]
    redirect_url = resolve_url(
        "import_route", data_source="switzerland_mobility", source_id=source_id
    )

    assertRedirects(response, redirect_url)
    assert mobility_cookies["mf-chmobil"] == "123"


def test_post_switzerland_mobility_login_import_id_bad(
    athlete, client, mock_login_response, mock_sm_routes_response
):
    url = reverse("switzerland_mobility_login")
    params = urlencode({"import": "bad_id"})
    data = {"username": "test_user", "password": "test_password"}
    mock_login_response()
    mock_sm_routes_response(athlete=athlete)
    response = client.post(f"{url}?{params}", data)

    mobility_cookies = client.session["switzerland_mobility_cookies"]
    redirect_url = resolve_url("import_routes", data_source="switzerland_mobility")

    assertRedirects(response, redirect_url)
    assert mobility_cookies["mf-chmobil"] == "123"


def test_post_switzerland_mobility_login_update_id(
    athlete, client, mock_login_response, mock_sm_route_response
):
    route = SwitzerlandMobilityRouteFactory(athlete=athlete)
    url = reverse("switzerland_mobility_login")
    params = urlencode({"update": route.id})
    data = {"username": athlete.user.username, "password": "test_password"}
    mock_login_response()
    mock_sm_route_response(source_id=route.source_id)
    response = client.post(f"{url}?{params}", data)

    mobility_cookies = client.session["switzerland_mobility_cookies"]
    redirect_url = route.get_absolute_url("update")

    assertRedirects(response, redirect_url)
    assert mobility_cookies["mf-chmobil"] == "123"


def test_post_switzerland_mobility_login_update_id_bad(
    athlete, client, mock_login_response, mock_sm_routes_response
):
    url = reverse("switzerland_mobility_login")
    params = urlencode({"update": "bad_id"})
    data = {"username": athlete.user.username, "password": "test_password"}
    mock_login_response()
    mock_sm_routes_response(athlete=athlete)
    response = client.post(f"{url}?{params}", data)

    mobility_cookies = client.session["switzerland_mobility_cookies"]
    redirect_url = resolve_url("import_routes", data_source="switzerland_mobility")

    assertRedirects(response, redirect_url)
    assert mobility_cookies["mf-chmobil"] == "123"


def test_post_switzerland_mobility_login_failed(
    athlete, client, mock_failed_login_response
):
    url = reverse("switzerland_mobility_login")
    data = {"username": "test_user", "password": "test_password"}
    mock_failed_login_response()
    response = client.post(url, data)

    assertContains(response, "Incorrect login.")
    assert "switzerland_mobility_cookies" not in client.session


def test_post_switzerland_mobility_login_server_error(
    athlete, client, mocked_responses, settings
):
    settings.SWITZERLAND_MOBILITY_LOGIN_URL = "https://example.com/login"
    url = reverse("switzerland_mobility_login")
    data = {"username": "test_user", "password": "test_password"}

    mocked_responses.add(
        responses.POST, settings.SWITZERLAND_MOBILITY_LOGIN_URL, status=500
    )
    response = client.post(url, data)

    content = "Error while logging-in to Switzerland Mobility."
    assertContains(response, content)


#####################
# view import_route #
#####################


def test_get_import_switzerland_mobility_route_with_checkpoints(
    athlete,
    client,
    switzerland_mobility_data_from_json,
    mock_import_route_call_response,
):
    route_json = "switzerland_mobility_route.json"
    geom, _ = switzerland_mobility_data_from_json(route_json)

    number_of_checkpoints = 5
    create_checkpoints_from_geom(geom, number_of_checkpoints)

    response = mock_import_route_call_response(
        data_source="switzerland_mobility",
        source_id=1234567,
        api_response_json=route_json,
        method="get",
    )

    checkpoint_choices = response.context["form"].fields["checkpoints"].choices
    assert len(checkpoint_choices) == number_of_checkpoints


def test_get_import_switzerland_mobility_route_redirect_to_login_with_import_id(
    athlete, client, mock_import_route_call_response
):
    source_id = 123456789
    response = mock_import_route_call_response(
        data_source="switzerland_mobility",
        source_id=source_id,
        api_response_json="403.json",
        api_response_status=403,
    )

    params = urlencode({"import": source_id})
    redirect_url = reverse("switzerland_mobility_login") + "?" + params
    assertRedirects(response, redirect_url)


def test_post_import_switzerland_mobility_route_no_checkpoints(
    athlete, client, mock_import_route_call_response
):
    source_id = 2191833
    route = SwitzerlandMobilityRouteFactory.build(source_id=source_id)

    post_data = get_route_post_data(route)
    response = mock_import_route_call_response(
        route.data_source,
        route.source_id,
        method="post",
        post_data=post_data,
    )

    route = SwitzerlandMobilityRoute.objects.get(source_id=source_id)
    assertRedirects(response, route.get_absolute_url())


def test_post_import_switzerland_mobility_route_with_checkpoints(
    athlete,
    client,
    switzerland_mobility_data_from_json,
    mock_import_route_call_response,
):
    route_json = "switzerland_mobility_route.json"
    geom, _ = switzerland_mobility_data_from_json(route_json)

    number_of_checkpoints = 5
    route = SwitzerlandMobilityRouteFactory.build()
    post_data = get_route_post_data(route)
    post_data["checkpoints"] = create_checkpoints_from_geom(geom, number_of_checkpoints)

    post_response = mock_import_route_call_response(
        data_source=route.data_source,
        source_id=route.source_id,
        api_response_json=route_json,
        method="post",
        post_data=post_data,
        follow_redirect=True,
    )

    # a new route has been created with the post response
    new_route = SwitzerlandMobilityRoute.objects.get(
        data_source=route.data_source, source_id=route.source_id, athlete=athlete
    )
    checkpoints = Checkpoint.objects.filter(route=new_route.pk)
    assert checkpoints.count() == number_of_checkpoints
    assertRedirects(post_response, new_route.get_absolute_url())


def test_post_import_switzerland_mobility_route_updated(
    athlete, mock_import_route_call_response
):
    route = SwitzerlandMobilityRouteFactory(
        source_id=2191833, athlete=athlete, start_place=None, end_place=None
    )

    post_data = get_route_post_data(route)
    response = mock_import_route_call_response(
        route.data_source,
        route.source_id,
        method="post",
        post_data=post_data,
        follow_redirect=True,
    )

    success_box = '<li class="box mrgv- alert success" >{message}</li>'.format(
        message=f"Route successfully updated from {route.DATA_SOURCE_NAME}"
    )
    assertRedirects(response, route.get_absolute_url())
    assertContains(response, success_box, html=True)


#####################
# view routes:route #
#####################


def test_get_switzerland_mobility_route_deleted_data(
    athlete, client, mock_sm_route_response
):
    route_id = 2191833
    route = SwitzerlandMobilityRouteFactory(source_id=route_id, athlete=athlete)

    # delete data file
    field = DataFrameField()
    file_path = field.storage.path(route.data.filepath)
    Path(file_path).unlink()

    # mock route details response
    mock_sm_route_response(route.source_id)
    response = client.get(route.get_absolute_url())

    assert response.status_code == 200


#####################
# view routes:update #
#####################


def test_get_update_switzerland_mobility_route_redirect_to_login_with_update_id(
    athlete, client, mock_sm_route_response
):
    route = SwitzerlandMobilityRouteFactory(athlete=athlete)
    url = route.get_absolute_url("update")
    mock_sm_route_response(
        source_id=route.source_id,
        api_response_json="403.json",
        api_response_status=403,
    )
    response = client.get(url)

    params = urlencode({"update": route.pk})
    redirect_url = reverse("switzerland_mobility_login") + "?" + params
    assertRedirects(response, redirect_url)
