from json import loads as json_loads
from os.path import dirname, join, realpath
from re import compile as re_compile

import httpretty
import requests
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.core.management.base import CommandError
from django.forms.models import model_to_dict
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.html import escape
from django.utils.six import StringIO
from pandas import DataFrame
from requests.exceptions import ConnectionError
from stravalib import Client as StravaClient

from . import factories
from ...routes.models import Athlete, Place, RoutePlace
from ...utils.factories import UserFactory
from ..forms import ImportersRouteForm, SwitzerlandMobilityLogin
from ..models import StravaRoute, Swissname3dPlace, SwitzerlandMobilityRoute
from ..models.switzerlandmobilityroute import request_json
from ..utils import get_strava_client


def load_data(file=''):
    dir_path = dirname(realpath(__file__))
    data_dir = 'data'
    path = join(
        dir_path,
        data_dir,
        file,
    )

    return open(path).read()


def raise_connection_error(self, request, uri, headers):
    """
    raises a connection error to use as the body of the mock
    response in httpretty. Unfortunately httpretty outputs to stdout:
    cf. https://stackoverflow.com/questions/36491664/silence-exceptions-that-do-not-result-in-test-failure-in-python-unittest
    """
    raise requests.ConnectionError('Connection error.')


@override_settings(
    STRAVA_CLIENT_TOKEN='1234567890123456789012345678901234567890'
)
class Strava(TestCase):
    """
    Test the Strava route importer.
    """

    def setUp(self):
        # Add user to the test database and log him in
        self.user = UserFactory(password='testpassword')
        self.client.login(username=self.user.username, password='testpassword')
        Athlete.objects.create(
            user=self.user,
            strava_token=settings.STRAVA_CLIENT_TOKEN,
        )

    def intercept_get_athlete(self, body=load_data('strava_athlete.json'),
                              status=200):
        """
        intercept the Strava API call to get_athlete. This call is made
        when creating the strava client to test if the API is
        available.
        """

        # athlete API call
        athlete_url = 'https://www.strava.com/api/v3/athlete'
        httpretty.register_uri(
            httpretty.GET, athlete_url,
            content_type="application/json", body=body,
            status=status
        )

    #########
    # Utils #
    #########

    def test_get_strava_client_success(self):
        # intercept API calls with httpretty
        httpretty.enable()
        self.intercept_get_athlete()
        strava_client = get_strava_client(self.user)
        httpretty.disable()

        self.assertIsInstance(strava_client, StravaClient)

    def test_get_strava_client_bad_token(self):
        self.user.athlete.strava_token = 'bad_token'
        httpretty.enable()
        self.intercept_get_athlete(
            body=load_data('strava_athlete_unauthorized.json'),
            status=401
        )

        with self.assertRaises(PermissionDenied):
            get_strava_client(self.user)

        httpretty.disable()

        self.assertTrue(self.user.athlete.strava_token is None)

    def test_get_strava_client_no_connection(self):
        # intercept API calls with httpretty
        httpretty.enable()

        self.intercept_get_athlete(
            body=raise_connection_error,
        )

        with self.assertRaises(ConnectionError):
            get_strava_client(self.user)

        self.assertFalse(self.user.athlete.strava_token is None)

    #########
    # Model #
    #########

    def test_data_from_streams(self):
        source_id = 2325453
        strava_client = StravaClient()
        strava_client.access_token = self.user.athlete.strava_token

        # intercept url with httpretty
        httpretty.enable()
        url = 'https://www.strava.com/api/v3/routes/%d/streams' % source_id
        streams_json = load_data('strava_streams.json')

        httpretty.register_uri(
            httpretty.GET, url,
            content_type="application/json", body=streams_json,
            status=200
        )

        streams = strava_client.get_route_streams(source_id)

        strava_route = factories.StravaRouteFactory()
        data = strava_route._data_from_streams(streams)
        nb_rows, nb_columns = data.shape

        httpretty.disable()

        self.assertIsInstance(data, DataFrame)
        self.assertEqual(nb_columns, 4)

    def test_set_activity_type(self):
        route = StravaRoute(source_id=2325453)
        strava_client = StravaClient()
        strava_client.access_token = self.user.athlete.strava_token

        httpretty.enable()
        # Route details API call
        route_detail_url = ('https://www.strava.com/api/v3/routes/%d'
                            % route.source_id)
        route_detail_json = load_data('strava_route_detail.json')

        httpretty.register_uri(
            httpretty.GET, route_detail_url,
            content_type="application/json", body=route_detail_json,
            status=200
        )

        route_streams_url = ('https://www.strava.com/api/v3/routes/%d/streams'
                             % route.source_id)
        streams_json = load_data('strava_streams.json')

        httpretty.register_uri(
            httpretty.GET, route_streams_url,
            content_type="application/json", body=streams_json,
            status=200
        )

        route.get_route_details(strava_client)
        httpretty.disable()

        self.assertEqual(route.activity_type_id, 1)

    #########
    # views #
    #########
    def test_redirect_when_token_missing(self):
        athlete = self.user.athlete
        athlete.strava_token = None
        athlete.save()

        routes_url = reverse('strava_routes')
        response = self.client.get(routes_url)
        connect_url = reverse('strava_connect')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, connect_url)

    def test_strava_routes_success(self):
        source_name = 'Strava'
        route_name = escape("Tout d'Aï")
        length = '12.9km'
        totalup = '1,880m+'

        # Intercept API calls with httpretty
        httpretty.enable()

        # Athlete API call
        self.intercept_get_athlete(body=load_data('strava_athlete.json'))

        # route list API call with athlete id from the athlete json file
        athlete_json = load_data('strava_athlete.json')
        athlete = json_loads(athlete_json)
        strava_athlete_id = athlete['id']

        route_list_url = ('https://www.strava.com/api/v3/athletes/%d/routes'
                          % strava_athlete_id)
        route_list_json = load_data('strava_route_list.json')
        httpretty.register_uri(
            httpretty.GET, route_list_url,
            content_type="application/json", body=route_list_json,
            status=200
        )

        url = reverse('strava_routes')
        response = self.client.get(url)
        response_content = response.content.decode('UTF-8')

        httpretty.disable()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(source_name in response_content)
        self.assertTrue(route_name in response_content)
        self.assertTrue(length in response_content)
        self.assertTrue(totalup in response_content)

    def test_strava_route_success(self):
        source_id = 2325453

        # intercept API calls with httpretty
        httpretty.enable()

        # Athlete API call
        self.intercept_get_athlete()

        # route details API call
        route_detail_url = ('https://www.strava.com/api/v3/routes/%d'
                            % source_id)
        route_detail_json = load_data('strava_route_detail.json')

        httpretty.register_uri(
            httpretty.GET, route_detail_url,
            content_type="application/json", body=route_detail_json,
            status=200
        )

        # route streams API call
        route_streams_url = ('https://www.strava.com/api/v3/routes/%d/streams'
                             % source_id)
        streams_json = load_data('strava_streams.json')

        httpretty.register_uri(
            httpretty.GET, route_streams_url,
            content_type="application/json", body=streams_json,
            status=200
        )

        url = reverse('strava_route', args=[source_id])
        response = self.client.get(url)
        response_content = response.content.decode('UTF-8')
        httpretty.disable()

        route_name = escape("Tout d'Aï")

        self.assertEqual(response.status_code, 200)
        self.assertIn(route_name, response_content)

    def test_strava_route_already_imported(self):
        source_id = 2325453
        factories.StravaRouteFactory(
            source_id=source_id,
            user=self.user,
        )

        # intercept API calls with httpretty
        httpretty.enable()

        # Athlete API call
        self.intercept_get_athlete()

        route_detail_url = ('https://www.strava.com/api/v3/routes/%d'
                            % source_id)
        route_detail_json = load_data('strava_route_detail.json')

        httpretty.register_uri(
            httpretty.GET, route_detail_url,
            content_type="application/json", body=route_detail_json,
            status=200
        )

        url = reverse('strava_route', args=[source_id])
        response = self.client.get(url)
        response_content = response.content.decode('UTF-8')

        httpretty.disable()

        already_imported = 'Already Imported'
        self.assertIn(already_imported, response_content)


@override_settings(
    SWITZERLAND_MOBILITY_LOGIN_URL='https://example.com/login',
    SWITZERLAND_MOBILITY_LIST_URL='https://example.com/tracks',
    SWITZERLAND_MOBILITY_META_URL='https://example.com/track/%d/getmeta',
    SWITZERLAND_MOBILITY_ROUTE_URL='https://example.com/track/%d/show'
)
class SwitzerlandMobility(TestCase):
    """
    Test the Switzerland Mobility route importer
    """

    def add_cookies_to_session(self):
        cookies = {'mf-chmobil': 'xxx', 'srv': 'yyy'}
        session = self.client.session
        session['switzerland_mobility_cookies'] = cookies
        session.save()
        return session

    def setUp(self):
        # Add user to the test database and log him in
        self.user = UserFactory(password='testpassword')
        self.client.login(username=self.user.username, password='testpassword')

    #########
    # Model #
    #########

    def test_request_json_success(self):
        # save cookies to session
        session = self.add_cookies_to_session()
        cookies = session['switzerland_mobility_cookies']

        url = 'https://testurl.ch'

        # intercept call with httpretty
        body = '[123456, "Test", null]'

        httpretty.enable()

        httpretty.register_uri(
            httpretty.GET, url,
            content_type="application/json", body=body,
            status=200
        )

        json_response, response = request_json(url, cookies)

        httpretty.disable()

        self.assertEqual(response['error'], False)
        self.assertEqual(response['message'], 'OK. ')
        self.assertEqual(json_loads(body), json_response)

    def test_request_json_server_error(self):
        # save cookies to session
        session = self.add_cookies_to_session()
        cookies = session['switzerland_mobility_cookies']

        url = 'https://testurl.ch'

        # intercept call with httpretty
        html_response = load_data(file='500.html')

        httpretty.enable()

        httpretty.register_uri(
            httpretty.GET, url,
            content_type="text/html", body=html_response,
            status=500
        )

        json_response, response = request_json(url, cookies)

        httpretty.disable()

        self.assertEqual(response['error'], True)
        self.assertTrue('500' in response['message'])
        self.assertEqual(json_response, False)

    def test_request_json_connection_error(self):
        # save cookies to session
        session = self.add_cookies_to_session()
        cookies = session['switzerland_mobility_cookies']
        url = 'https://testurl.ch'
        message = "Connection Error: could not connect to %s. " % url

        # intercept call with httpretty
        httpretty.enable()

        httpretty.register_uri(
            httpretty.GET, url, body=raise_connection_error,
        )

        json_response, response = request_json(url, cookies)

        httpretty.disable()

        self.assertEqual(response['error'], True)
        self.assertIn(message, response['message'])
        self.assertEqual(json_response, False)

    def test_get_raw_remote_routes_success(self):
        # save cookies to session
        session = self.add_cookies_to_session()

        # intercept call to map.wandland.ch with httpretty
        httpretty.enable()
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        json_response = load_data('tracks_list.json')

        httpretty.register_uri(
            httpretty.GET, routes_list_url,
            content_type="application/json", body=json_response,
            status=200
        )
        raw_routes, response = SwitzerlandMobilityRoute.objects.get_raw_remote_routes(
            session)
        httpretty.disable()

        self.assertEqual(len(raw_routes), 37)
        self.assertEqual(response['error'], False)
        self.assertEqual(response['message'], 'OK. ')

    def test_get_raw_remote_routes_empty(self):
        # save cookies to session
        session = self.add_cookies_to_session()

        # intercept call to map.wandland.ch with httpretty
        httpretty.enable()
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        json_response = '[]'

        httpretty.register_uri(
            httpretty.GET, routes_list_url,
            content_type="application/json", body=json_response,
            status=200
        )
        raw_routes, response = SwitzerlandMobilityRoute.objects.get_raw_remote_routes(
            session)
        httpretty.disable()

        self.assertEqual(len(raw_routes), 0)
        self.assertEqual(response['error'], False)
        self.assertEqual(response['message'], 'OK. ')

    def test_get_raw_remote_routes_server_error(self):
        # save cookies to session
        session = self.add_cookies_to_session()

        # intercept call to map.wandland.ch with httpretty
        httpretty.enable()
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        json_response = '[]'

        httpretty.register_uri(
            httpretty.GET, routes_list_url,
            content_type="application/json", body=json_response,
            status=500
        )
        raw_routes, response = SwitzerlandMobilityRoute.objects.get_raw_remote_routes(
            session)
        httpretty.disable()

        expected_message = (
            'Error 500: could not retrieve information from %s. '
            % routes_list_url
        )

        self.assertEqual(raw_routes, False)
        self.assertEqual(response['error'], True)
        self.assertEqual(response['message'], expected_message)

    def test_get_raw_remote_routes_connection_error(self):

        # save cookies to session
        session = self.add_cookies_to_session()

        # intercept call to map.wandland.ch with httpretty
        httpretty.enable()
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL

        httpretty.register_uri(
            httpretty.GET, routes_list_url,
            content_type="application/json", body=raise_connection_error
        )

        raw_routes, response = SwitzerlandMobilityRoute.objects.get_raw_remote_routes(
            session)
        httpretty.disable()

        expected_message = (
            'Connection Error: could not connect to %s. '
            % routes_list_url
        )

        self.assertEqual(raw_routes, False)
        self.assertEqual(response['error'], True)
        self.assertIn(expected_message, response['message'])

    def test_format_raw_remote_routes_success(self):
        raw_routes = json_loads(load_data(file='tracks_list.json'))

        formatted_routes = SwitzerlandMobilityRoute.objects.format_raw_remote_routes(
            raw_routes)

        self.assertTrue(type(formatted_routes) is list)
        self.assertEqual(len(formatted_routes), 37)
        for route in formatted_routes:
            self.assertTrue(isinstance(route, SwitzerlandMobilityRoute))
            self.assertEqual(route.description, '')

    def test_format_raw_remote_routes_empty(self):
        raw_routes = []

        formatted_routes = SwitzerlandMobilityRoute.objects.format_raw_remote_routes(
            raw_routes)

        self.assertEqual(len(formatted_routes), 0)
        self.assertTrue(type(formatted_routes) is list)

    def test_add_route_meta_success(self):
        route = {'name': 'Haute Cime', 'id': 2191833, 'description': ''}
        route_meta_url = settings.SWITZERLAND_MOBILITY_META_URL % route['id']

        # Turn the route meta URL into a regular expression
        route_meta_url = re_compile(
            route_meta_url.replace(str(route['id']), '(\d+)'))

        httpretty.enable()

        route_json = load_data('track_info.json')

        httpretty.register_uri(
            httpretty.GET, route_meta_url,
            content_type="application/json", body=route_json,
            status=200
        )

        route_with_meta, route_response = SwitzerlandMobilityRoute.objects.\
            add_route_remote_meta(route)

        self.assertEqual(route_with_meta['totalup'].m, 1234.5)
        self.assertEqual(route_response['message'], 'OK. ')

    def test_check_for_existing_routes_success(self):

        user = UserFactory()

        # save an existing route
        factories.RouteFactory(
            source_id=2191833,
            data_source='switzerland_mobility',
            name='Haute Cime',
            user=user,
        )

        formatted_routes = [
            SwitzerlandMobilityRoute(
                name='Haute Cime',
                source_id=2191833,
                description=''
            ),
            SwitzerlandMobilityRoute(
                name='Grammont',
                source_id=2433141,
                description=''
            ),
            SwitzerlandMobilityRoute(
                name='Rochers de Nayes',
                source_id=2692136,
                description=''
            ),
            SwitzerlandMobilityRoute(
                name='Villeneuve - Leysin',
                source_id=3011765,
                description=''
            )]

        new_routes, old_routes = SwitzerlandMobilityRoute.objects.check_for_existing_routes(
            user=user,
            routes=formatted_routes,
            data_source='switzerland_mobility'
        )

        self.assertEqual(len(new_routes), 3)
        self.assertEqual(len(old_routes), 1)

    def test_get_remote_routes_success(self):
        # save cookies to session
        session = self.add_cookies_to_session()
        user = UserFactory()

        # save an existing route
        factories.SwitzerlandMobilityRouteFactory(
            user=user,
        )

        # intercept routes_list call to map.wandland.ch with httpretty
        httpretty.enable()
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        json_response = load_data('tracks_list.json')

        httpretty.register_uri(
            httpretty.GET, routes_list_url,
            content_type="application/json", body=json_response,
            status=200
        )

        # intercept getmeta call to map.wandland.ch with httpretty
        # remove "https://
        route_meta_url = settings.SWITZERLAND_MOBILITY_META_URL[8:]
        # Turn the route meta URL into a regular expression
        route_meta_url = re_compile(route_meta_url.replace('%d', '(\w+)'))

        route_json = load_data('track_info.json')

        httpretty.register_uri(
            httpretty.GET, route_meta_url,
            content_type="application/json", body=route_json,
            status=200
        )

        new_routes, old_routes, response = SwitzerlandMobilityRoute.objects.\
            get_remote_routes(session, user)
        httpretty.disable()

        self.assertEqual(len(new_routes), 36)
        self.assertEqual(len(old_routes), 1)
        self.assertEqual(response['error'], False)

    def test_get_raw_route_details_success(self):
        route_id = 2191833
        route = SwitzerlandMobilityRoute(source_id=route_id)

        # intercept routes_list call to map.wandland.ch with httpretty
        httpretty.enable()
        route_url = settings.SWITZERLAND_MOBILITY_ROUTE_URL % route_id

        route_details_json = load_data(file='2191833_show.json')

        httpretty.register_uri(
            httpretty.GET, route_url,
            content_type="application/json", body=route_details_json,
            status=200
        )

        route_raw_json, response = route.get_raw_route_details(route_id)

        httpretty.disable()

        self.assertEqual('Haute Cime', route_raw_json['properties']['name'])
        self.assertEqual(response['error'], False)

    def test_get_raw_route_details_error(self):
        route_id = 999999999
        route = SwitzerlandMobilityRoute(source_id=route_id)

        # intercept routes_list call to map.wandland.ch with httpretty
        httpretty.enable()
        route_url = settings.SWITZERLAND_MOBILITY_ROUTE_URL % route_id

        html_response = load_data(file='404.html')

        httpretty.register_uri(
            httpretty.GET, route_url,
            content_type="text/html", body=html_response,
            status=404
        )

        route_raw_json, response = route.get_raw_route_details(route_id)

        httpretty.disable()

        self.assertEqual(False, route_raw_json)
        self.assertEqual(response['error'], True)
        self.assertTrue('404' in response['message'])

    def test_already_imported(self):
        route = factories.SwitzerlandMobilityRouteFactory.build()
        self.assertEqual(route.already_imported(), False)
        route = factories.SwitzerlandMobilityRouteFactory()
        self.assertEqual(route.already_imported(), True)

    #########
    # Views #
    #########

    def test_importers_index_not_logged_redirected(self):
        self.client.logout()
        url = reverse('importers_index')
        redirect_url = "/login/?next=" + url
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_importers_index_view_logged_in(self):
        content = 'Import routes'
        url = reverse('importers_index')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(content in str(response.content))

    def test_switzerland_mobility_route_success(self):
        route_id = 2823968
        url = reverse('switzerland_mobility_route', args=[route_id])

        # intercept call to Switzerland Mobility with httpretty
        httpretty.enable()
        details_json_url = settings.SWITZERLAND_MOBILITY_ROUTE_URL % route_id
        json_response = load_data(file='2191833_show.json')

        httpretty.register_uri(
            httpretty.GET, details_json_url,
            content_type="application/json", body=json_response,
            status=200
        )

        response = self.client.get(url)

        httpretty.disable()

        title = '<title>Home by Two - Import Haute Cime</title>'
        start_place_form = (
            '<select name="route-start_place" '
            'id="id_route-start_place">'
        )
        places_formset = (
            '<input type="hidden" name="places-TOTAL_FORMS" '
            'value="0" id="id_places-TOTAL_FORMS" />'
        )

        map_data = '<div id="main" class="leaflet-container-default"></div>'

        self.assertEqual(response.status_code, 200)
        self.assertTrue(title in str(response.content))
        self.assertTrue(start_place_form in str(response.content))
        self.assertTrue(places_formset in str(response.content))
        self.assertTrue(map_data in str(response.content))

    def test_switzerland_mobility_route_already_imported(self):
        route_id = 2733343
        factories.SwitzerlandMobilityRouteFactory(
            source_id=route_id,
            user=self.user,
        )

        url = reverse('switzerland_mobility_route', args=[route_id])
        content = 'Already Imported'

        # intercept call to Switzerland Mobility with httpretty
        httpretty.enable()
        details_json_url = settings.SWITZERLAND_MOBILITY_ROUTE_URL % route_id
        json_response = load_data(file='2733343_show.json')

        httpretty.register_uri(
            httpretty.GET, details_json_url,
            content_type="application/json", body=json_response,
            status=200
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(content in str(response.content))

    def test_switzerland_mobility_route_server_error(self):
        route_id = 999999999999
        url = reverse('switzerland_mobility_route', args=[route_id])
        content = 'Error 500'

        # intercept call to Switzerland Mobility with httpretty
        httpretty.enable()
        details_json_url = settings.SWITZERLAND_MOBILITY_ROUTE_URL % route_id
        html_response = load_data(file='500.html')

        httpretty.register_uri(
            httpretty.GET, details_json_url,
            content_type="text/html", body=html_response,
            status=500
        )

        response = self.client.get(url)

        httpretty.disable()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(content in str(response.content))

    def test_switzerland_mobility_route_post_success_no_places(self):
        route_id = 2191833
        route = factories.SwitzerlandMobilityRouteFactory.build(
            source_id=route_id
        )

        start_place = route.start_place
        start_place.save()
        end_place = route.end_place
        end_place.save()

        route_data = model_to_dict(route)
        post_data = {
            'route-' + key: value
            for key, value in route_data.items()
        }
        del(post_data['route-image'])

        post_data.update({
            'route-activity_type': 1,
            'route-start_place': start_place.id,
            'route-end_place': end_place.id,
            'route-geom': route.geom.wkt,
            'route-data': route.data.to_json(orient='records'),
            'places-TOTAL_FORMS': 0,
            'places-INITIAL_FORMS': 0,
            'places-MIN_NUM_FORMS': 0,
            'places-MAX_NUM_FORMS': 1000,
        })

        url = reverse('switzerland_mobility_route', args=[route_id])
        response = self.client.post(url, post_data)

        route = SwitzerlandMobilityRoute.objects.get(source_id=route_id)
        redirect_url = reverse('routes:route', args=[route.id])

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_switzerland_mobility_route_post_success_place(self):
        route_id = 2191833
        route = factories.SwitzerlandMobilityRouteFactory.build(
            source_id=route_id
        )

        start_place = route.start_place
        start_place.save()
        end_place = route.end_place
        end_place.save()

        route_data = model_to_dict(route)
        post_data = {
            'route-' + key: value
            for key, value in route_data.items()
        }
        del(post_data['route-image'])

        post_data.update({
            'route-activity_type': 1,
            'route-start_place': start_place.id,
            'route-end_place': end_place.id,
            'route-geom': route.geom.wkt,
            'route-data': route.data.to_json(orient='records'),
            'places-TOTAL_FORMS': 2,
            'places-INITIAL_FORMS': 0,
            'places-MIN_NUM_FORMS': 0,
            'places-MAX_NUM_FORMS': 1000,
            'places-0-place': start_place.id,
            'places-0-line_location': 0.0207291870756597,
            'places-0-altitude_on_route': 123,
            'places-0-id': '',
            'places-0-include': True,
            'places-1-place': end_place.id,
            'places-1-line_location': 0.039107325861928,
            'places-1-altitude_on_route': 123,
            'places-1-id': '',
            'places-1-include': True,
        })

        url = reverse('switzerland_mobility_route', args=[route_id])
        response = self.client.post(url, post_data)

        # a new route has been created
        route = SwitzerlandMobilityRoute.objects.get(source_id=route_id)
        route_places = RoutePlace.objects.filter(route=route.id)
        self.assertEqual(route_places.count(), 2)

        redirect_url = reverse('routes:route', args=[route.id])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_switzerland_mobility_route_post_no_validation_places(self):
        route_id = 2191833
        route = factories.SwitzerlandMobilityRouteFactory.build(
            source_id=route_id
        )

        start_place = route.start_place
        start_place.save()
        end_place = route.end_place
        end_place.save()

        route_data = model_to_dict(route)
        post_data = {
            'route-' + key: value
            for key, value in route_data.items()
        }
        del(post_data['route-image'])

        post_data.update({
            'route-activity_type': 1,
            'route-start_place': start_place.id,
            'route-end_place': end_place.id,
            'route-geom': route.geom.wkt,
            'route-data': route.data.to_json(orient='records'),
            'places-TOTAL_FORMS': 2,
            'places-INITIAL_FORMS': 0,
            'places-MIN_NUM_FORMS': 0,
            'places-MAX_NUM_FORMS': 1000,
            'places-0-place': start_place.id,
            'places-0-altitude_on_route': 'not a number',
            'places-0-id': '',
            'places-1-place': end_place.id,
            'places-1-line_location': 0.039107325861928,
            'places-1-altitude_on_route': 123,
            'places-1-id': '',
        })

        url = reverse('switzerland_mobility_route', args=[route_id])
        response = self.client.post(url, post_data)
        alert_box = '<div class="box alert alert--error">'
        required_field = 'This field is required.'
        not_a_number = 'Enter a number.'

        self.assertEqual(response.status_code, 200)
        self.assertTrue(alert_box in str(response.content))
        self.assertTrue(required_field in str(response.content))
        self.assertTrue(not_a_number in str(response.content))

    def test_switzerland_mobility_route_post_integrity_error(self):
        route_id = 2191833
        route = factories.SwitzerlandMobilityRouteFactory(
            source_id=route_id,
            user=self.user,
        )

        start_place = route.start_place
        end_place = route.end_place

        route_data = model_to_dict(route)
        post_data = {
            'route-' + key: value
            for key, value in route_data.items()
        }

        del(post_data['route-image'])

        post_data.update({
            'route-start_place': start_place.id,
            'route-end_place': end_place.id,
            'route-geom': route.geom.wkt,
            'route-data': route.data.to_json(orient='records'),
            'places-TOTAL_FORMS': 2,
            'places-INITIAL_FORMS': 0,
            'places-MIN_NUM_FORMS': 0,
            'places-MAX_NUM_FORMS': 1000,
            'places-0-place': start_place.id,
            'places-0-line_location': 0.0207291870756597,
            'places-0-altitude_on_route': 123,
            'places-0-id': '',
            'places-1-place': end_place.id,
            'places-1-line_location': 0.039107325861928,
            'places-1-altitude_on_route': 123,
            'places-1-id': '',
        })

        url = reverse('switzerland_mobility_route', args=[route_id])
        response = self.client.post(url, post_data)

        alert_box = '<div class="box alert alert--error">'
        integrity_error = (
            'Integrity Error: duplicate key value violates unique constraint'
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(alert_box in str(response.content))
        self.assertTrue(integrity_error in str(response.content))

    def test_switzerland_mobility_routes_success(self):
        url = reverse('switzerland_mobility_routes')
        content = 'Import Routes from Switzerland Mobility Plus'
        self.add_cookies_to_session()

        # intercept call to map.wanderland.ch
        httpretty.enable()
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        json_response = load_data(file='tracks_list.json')

        httpretty.register_uri(
            httpretty.GET, routes_list_url,
            content_type="application/json", body=json_response,
            status=200
        )

        response = self.client.get(url)

        httpretty.disable()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(content in str(response.content))

    def test_switzerland_mobility_routes_error(self):
        url = reverse('switzerland_mobility_routes')
        self.add_cookies_to_session()

        # intercept call to map.wanderland.ch
        httpretty.enable()
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        json_response = ('[]')

        httpretty.register_uri(
            httpretty.GET, routes_list_url,
            content_type="application/json", body=json_response,
            status=500
        )

        response = self.client.get(url)
        response_content = response.content.decode('UTF-8')

        httpretty.disable()
        content = ('Error 500: could not retrieve information from %s. '
                   % routes_list_url)

        self.assertEqual(response.status_code, 200)
        self.assertIn(content, response_content)

    def test_switzerland_mobility_routes_no_cookies(self):
        url = reverse('switzerland_mobility_routes')
        redirect_url = reverse('switzerland_mobility_login')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_switzerland_mobility_get_login_view(self):
        url = reverse('switzerland_mobility_login')
        content = 'action="%s"' % url
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(content in str(response.content))

    def test_switzerland_mobility_login_successful(self):
        url = reverse('switzerland_mobility_login')
        data = {'username': 'testuser', 'password': 'testpassword'}

        # intercept call to map.wandland.ch with httpretty
        httpretty.enable()
        login_url = settings.SWITZERLAND_MOBILITY_LOGIN_URL
        # successful login response
        json_response = '{"loginErrorMsg": "", "loginErrorCode": 200}'
        adding_headers = {'Set-Cookie': 'mf-chmobil=xxx'}

        httpretty.register_uri(
            httpretty.POST, login_url,
            content_type="application/json", body=json_response,
            status=200, adding_headers=adding_headers
        )
        response = self.client.post(url, data)
        httpretty.disable()

        mobility_cookies = self.client.session['switzerland_mobility_cookies']

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('switzerland_mobility_routes'))
        self.assertEqual(mobility_cookies['mf-chmobil'], 'xxx')

    def test_switzerland_mobility_login_failed(self):
        url = reverse('switzerland_mobility_login')
        data = {'username': 'testuser', 'password': 'testpassword'}

        # intercept call to map.wandland.ch with httpretty
        httpretty.enable()
        login_url = settings.SWITZERLAND_MOBILITY_LOGIN_URL
        # failed login response
        json_response = (
            '{"loginErrorMsg": "Incorrect login.", '
            '"loginErrorCode": 500}'
        )

        httpretty.register_uri(
            httpretty.POST, login_url,
            content_type="application/json", body=json_response,
            status=200
        )
        response = self.client.post(url, data)
        httpretty.disable()

        self.assertEqual(response.status_code, 200)
        self.assertTrue('Incorrect login.' in str(response.content))
        with self.assertRaises(KeyError):
            self.client.session['switzerland_mobility_cookies']

    def test_switzerland_mobility_login_server_error(self):
        url = reverse('switzerland_mobility_login')
        data = {'username': 'testuser', 'password': 'testpassword'}
        content = 'Error 500: logging to Switzeland Mobility.'

        # intercept call to map.wandland.ch with httpretty
        httpretty.enable()
        login_url = settings.SWITZERLAND_MOBILITY_LOGIN_URL
        httpretty.register_uri(httpretty.POST, login_url, status=500)

        response = self.client.post(url, data)
        httpretty.disable()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(content in str(response.content))

    #########
    # Forms #
    #########

    def test_switzerland_mobility_valid_login_form(self):
        username = 'test@test.com'
        password = '123456'
        data = {'username': username, 'password': password}
        form = SwitzerlandMobilityLogin(data=data)

        self.assertTrue(form.is_valid())

    def test_switzerland_mobility_invalid_login_form(self):
        username = ''
        password = ''
        data = {'username': username, 'password': password}
        form = SwitzerlandMobilityLogin(data=data)

        self.assertFalse(form.is_valid())

    def test_switzerland_mobility_valid_model_form(self):
        route = factories.SwitzerlandMobilityRouteFactory.build()
        route_data = model_to_dict(route)
        route_data.update({
            'activity_type': 1,
            'geom': route.geom.wkt,
            'data': route.data.to_json(orient='records'),
            'start_place': route.start_place.id,
            'end_place': route.end_place.id
        })
        form = ImportersRouteForm(data=route_data)
        self.assertTrue(form.is_valid())

    def test_switzerland_mobility_invalid_model_form(self):
        route = factories.SwitzerlandMobilityRouteFactory.build()
        route_data = model_to_dict(route)
        route_data.update({
            'geom': route.geom.wkt,
            'start_place': route.start_place.id,
            'end_place': route.end_place.id
        })
        del route_data['geom']
        form = ImportersRouteForm(data=route_data)
        self.assertFalse(form.is_valid())


class Swissname3dModelTest(TestCase):
    """
    Test the Swissname3d Model,
    a Proxy Model to import from the Swissname3d data set
    """

    def get_place_data(self, data_source='swissname3d'):
        data = {
            'swissname3d': {
                'place_type': 'Gipfel',
                'name': 'Place3D_name',
                'description': 'Place3D_description',
                'altitude': 666,
                'public_transport': False,
                'source_id': '1',
                'geom': 'POINT(0 0)',
            },

            'homebytwo': {
                'place_type': 'Church',
                'name': 'Other_Name',
                'description': 'Other_description',
                'altitude': 1000,
                'public_transport': True,
                'geom': 'POINT(0 0)',
            },
        }

        return data[data_source]

    def get_path_to_data(self, file_type='shp'):
        dir_path = dirname(realpath(__file__))

        if file_type == 'shp':
            # Test file with 35 features only
            shapefile = join(
                dir_path,
                'data',
                'TestSwissNAMES3D_PKT.shp'
            )
            return shapefile

        else:
            # Bad empty data
            text_data = join(dir_path, 'data', 'text.txt')
            return text_data

    def test_create_instance(self):
        place3d = Swissname3dPlace(**self.get_place_data())
        self.assertEqual('Place3D_name', str(place3d))

    def test_save_instance(self):
        place3d = Swissname3dPlace(**self.get_place_data())
        place3d.save()
        self.assertEqual(Swissname3dPlace.objects.count(), 1)

    def test_separate_from_other_place_models(self):
        place3d = Swissname3dPlace(**self.get_place_data())
        place3d.save()
        other_place = Place(**self.get_place_data('homebytwo'))
        other_place.save()
        self.assertEqual(Swissname3dPlace.objects.count(), 1)
        self.assertEqual(Place.objects.count(), 2)

    def test_prevent_duplicate_entries(self):
        place3d_1 = Swissname3dPlace(**self.get_place_data())
        place3d_1.save()

        place3d_2 = Swissname3dPlace(**self.get_place_data())
        place3d_2.name = 'Other_3D_place'
        place3d_2.save()
        self.assertEqual(Place.objects.count(), 1)

        place3d_3 = Swissname3dPlace(**self.get_place_data())
        place3d_3.source_id = '2'
        place3d_3.save()
        self.assertEqual(Place.objects.count(), 2)

    # Management Commands
    def test_command_output_inexistant_file(self):
        with self.assertRaises(OSError):
            call_command('importswissname3d', 'toto')

    def test_command_output_incorrect_shapefile(self):
        with self.assertRaises(CommandError):
            call_command('importswissname3d', self.get_path_to_data('bad'))

    def test_command_output_correct_shapefile(self):
        out = StringIO()
        call_command('importswissname3d', self.get_path_to_data('shp'),
                     '--no-input', stdout=out)
        self.assertTrue('Successfully imported' in out.getvalue())

    def test_command_limit_option(self):
        out = StringIO()
        call_command('importswissname3d', '--limit', '10',
                     '--no-input', self.get_path_to_data('shp'), stdout=out)
        self.assertTrue('Successfully imported 10 places' in out.getvalue())
        self.assertEqual(Swissname3dPlace.objects.count(), 10)

    def test_command_limit_higher_than_feature_count(self):
        out = StringIO()
        call_command('importswissname3d', '--limit', '100',
                     '--no-input', self.get_path_to_data('shp'), stdout=out)
        self.assertTrue('Successfully imported 35 places' in out.getvalue())
        self.assertEqual(Swissname3dPlace.objects.count(), 35)

    def test_command_limit_delete_replace_option(self):
        out = StringIO()
        call_command('importswissname3d', '--limit', '10',
                     '--no-input', self.get_path_to_data('shp'), stdout=out)
        call_command('importswissname3d', '--delete',
                     '--no-input', self.get_path_to_data('shp'), stdout=out)
        self.assertIn('Successfully deleted 10 places.', out.getvalue())
        self.assertIn('Successfully imported 35 places.', out.getvalue())
        self.assertEqual(Swissname3dPlace.objects.count(), 35)

    def test_command_delete_swissname3d_only(self):
        out = StringIO()
        place3d = Swissname3dPlace(**self.get_place_data())
        place3d.save()
        place = Place(**self.get_place_data('homebytwo'))
        place.save()
        self.assertEqual(Place.objects.count(), 2)  # 1 + 1
        self.assertEqual(Swissname3dPlace.objects.count(), 1)
        call_command('importswissname3d', '--delete',
                     '--no-input', self.get_path_to_data('shp'), stdout=out)
        self.assertEqual(Place.objects.count(), 36)  # 35 + 1
        self.assertEqual(Swissname3dPlace.objects.count(), 35)
