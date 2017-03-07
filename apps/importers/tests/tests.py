from django.core.management import call_command
from django.core.management.base import CommandError
from django.conf import settings
from django.test import TestCase, override_settings
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.utils.six import StringIO

from ..models import Swissname3dPlace, SwitzerlandMobilityRoute
from ..forms import SwitzerlandMobilityLogin, SwitzerlandMobilityRouteForm
from apps.routes.models import Place, RoutePlace

import os
import httpretty
import re
import requests
import json
import pandas as pd
import numpy as np


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

    def raise_connection_error(self, request, uri, headers):

        # raise connection error
        raise requests.ConnectionError('Connection error.')

    def setUp(self):
        # Add user to the test database
        self.user = User.objects.create_user(
            'testuser',
            'test@test.com',
            'test'
        )

        start_place = Place(
            place_type='Train Station',
            name='Start_Place',
            description='Place_description',
            altitude=500,
            public_transport=True,
            geom='POINT(0 0)',
        )
        start_place.save()

        end_place = Place(
            place_type='Train Station',
            name='End_Place',
            description='Place_description',
            altitude=1500,
            public_transport=True,
            geom='POINT(2000 2000)',
        )
        end_place.save()

        # Login the test user
        self.client.login(username='testuser', password='test')

        self.route_data = {
                'name': 'Haute-Cime',
                'user': self.user,
                'source_id': 2191833,
                'length': 10,
                'totalup': 100,
                'totaldown': 100,
                'geom': 'LINESTRING(0 0, 2000 2000)',
                'start_place': start_place,
                'end_place': end_place,
                'data': pd.DataFrame(
                    np.random.randn(8, 4),
                    columns=['lat', 'lng', 'altitude', 'length']
                )
        }

        self.route_details_json = (
            '{"geometry": {'
            '        "type": "LineString",'
            '        "coordinates": [[612190.0, 129403.0], '
            '[615424.648017, 129784.662852]]'
            '    },'
            '    "type": "Feature",'
            '    "properties": {'
            '        "profile": "[[612190, 129403, 727.9, 0], '
            '[612190.643986, 129401.568195, 727.200081846, 1.56996290599]]",'
            '        "gpspoints": 0,'
            '        "imported": null,'
            '        "opacity": 100,'
            '        "name": "Leuk Bridge",'
            '        "original_id": 1596570,'
            '        "via_points": "[[612190, 129403], '
            '[612190.643986, 129401.568195]]",'
            '        "timetype": "velo",'
            '        "meta": {'
            '            "heightdiff": 220.7,'
            '            "walking": 95.7930478068,'
            '            "elemax": 893.53,'
            '            "length": 6047.5,'
            '            "time": {'
            '                "btime": 52.5323191067,'
            '                "wtime": 103.274652268'
            '            },'
            '            "elevationmodels": "ElevationModel Snapped",'
            '            "totalup": 214.3,'
            '            "biking": 68.075451661,'
            '            "elemin": 724.200006399,'
            '            "totaldown": 48.7'
            '        },'
            '        "owner": "100000026329",'
            '        "velospeed": 15'
            '    },'
            '    "id": 2191833'
            '}')

        self.html_404 = (
            '<!DOCTYPE html>'
            '<html>'
            '  <head>'
            '    <title>404 not found</title>'
            '  </head>'
            '  <body>'
            '    <h1>Error 404 not found</h1>'
            '    <p>not found</p>'
            '    <h3>Guru Meditation:</h3>'
            '    <p>XID: 371278956</p>'
            '    <hr>'
            '    <p>Varnish cache server</p>'
            '  </body>'
            '</html>')

        self.html_500 = (
            '<html>'
            '  <head>'
            '   <title>500 Internal Server Error</title>'
            '  </head>'
            '  <body>'
            '   <h1>500 Internal Server Error</h1>'
            '   The server has either erred or '
            'is incapable of performing the requested operation.<br/><br/>'
            '  </body>'
            ' </html>')

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

        json_response, response = SwitzerlandMobilityRoute.objects.\
            request_json(url, cookies)

        httpretty.disable()

        self.assertEqual(response['error'], False)
        self.assertEqual(response['message'], 'OK. ')
        self.assertEqual(json.loads(body), json_response)

    def test_request_json_server_error(self):
        # save cookies to session
        session = self.add_cookies_to_session()
        cookies = session['switzerland_mobility_cookies']

        url = 'https://testurl.ch'

        # intercept call with httpretty
        html_response = self.html_500

        httpretty.enable()

        httpretty.register_uri(
            httpretty.GET, url,
            content_type="text/html", body=html_response,
            status=500
        )

        json_response, response = SwitzerlandMobilityRoute.objects.\
            request_json(url, cookies)

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
        body = self.raise_connection_error

        httpretty.enable()

        httpretty.register_uri(
            httpretty.GET, url, body=body,
        )

        json_response, response = SwitzerlandMobilityRoute.objects.\
            request_json(url, cookies)

        httpretty.disable()

        self.assertEqual(response['error'], True)
        self.assertEqual(message, response['message'])
        self.assertEqual(json_response, False)

    def test_get_raw_remote_routes_success(self):
        # save cookies to session
        session = self.add_cookies_to_session()

        # intercept call to map.wandland.ch with httpretty
        httpretty.enable()
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        json_response = (
            '[[2191833, "Haute Cime", null], '
            '[2433141, "Grammont", null], '
            '[2692136, "Rochers de Nayes", null], '
            '[3011765, "Villeneuve - Leysin", null]]'
        )

        httpretty.register_uri(
            httpretty.GET, routes_list_url,
            content_type="application/json", body=json_response,
            status=200
        )
        raw_routes, response = SwitzerlandMobilityRoute.objects.\
            get_raw_remote_routes(session)
        httpretty.disable()

        self.assertEqual(len(raw_routes), 4)
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
        raw_routes, response = SwitzerlandMobilityRoute.objects.\
            get_raw_remote_routes(session)
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
        raw_routes, response = SwitzerlandMobilityRoute.objects.\
            get_raw_remote_routes(session)
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
        body = self.raise_connection_error

        httpretty.register_uri(
            httpretty.GET, routes_list_url,
            content_type="application/json", body=body
        )

        raw_routes, response = SwitzerlandMobilityRoute.objects.\
            get_raw_remote_routes(session)
        httpretty.disable()

        expected_message = (
            'Connection Error: could not connect to %s. '
            % routes_list_url
        )

        self.assertEqual(raw_routes, False)
        self.assertEqual(response['error'], True)
        self.assertEqual(response['message'], expected_message)

    def test_format_raw_remote_routes_success(self):
        raw_routes = [
            [2191833, 'Haute Cime', None],
            [2433141, 'Grammont', None],
            [2692136, 'Rochers de Nayes', None],
            [3011765, 'Villeneuve - Leysin', None]
        ]

        formatted_routes = SwitzerlandMobilityRoute.objects.\
            format_raw_remote_routes(raw_routes)

        self.assertTrue(type(formatted_routes) is list)
        self.assertEqual(len(formatted_routes), 4)
        for route in formatted_routes:
            self.assertTrue(type(route) is dict)
            self.assertEqual(route['description'], '')

    def test_format_raw_remote_routes_empty(self):
        raw_routes = []

        formatted_routes = SwitzerlandMobilityRoute.objects.\
            format_raw_remote_routes(raw_routes)

        self.assertEqual(len(formatted_routes), 0)
        self.assertTrue(type(formatted_routes) is list)

    def test_add_route_meta_success(self):
        route = {'name': 'Haute Cime', 'id': 2191833, 'description': ''}
        route_meta_url = settings.SWITZERLAND_MOBILITY_META_URL % route['id']

        # Turn the route meta URL into a regular expression
        route_meta_url = re.compile(route_meta_url.replace(
            str(route['id']), '(\d+)'))

        httpretty.enable()

        route_json = (
            '{"length": 12345.6,'
            '"time":'
            '    {"btime": 50.123456789,'
            '    "wtime": 100.123456789},'
            '"totalup": 1234.5,'
            '"totaldown": 4321.0}'
        )

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
        formatted_routes = [
            {'name': 'Haute Cime', 'id': 2191833, 'description': ''},
            {'name': 'Grammont', 'id': 2433141, 'description': ''},
            {'name': 'Rochers de Nayes', 'id': 2692136, 'description': ''},
            {'name': 'Villeneuve - Leysin', 'id': 3011765, 'description': ''}]

        user = User.objects.filter(username='testuser')

        # save an existing route
        route = SwitzerlandMobilityRoute(**self.route_data)
        route.save()

        new_routes, old_routes = SwitzerlandMobilityRoute.objects.\
            check_for_existing_routes(
                formatted_routes,
                user,
            )

        self.assertEqual(len(new_routes), 3)
        self.assertEqual(len(old_routes), 1)

    def test_get_remote_routes_success(self):
        # save cookies to session
        session = self.add_cookies_to_session()

        user = User.objects.filter(username='testuser')

        # save an existing route
        route = SwitzerlandMobilityRoute(**self.route_data)
        route.save()

        # intercept routes_list call to map.wandland.ch with httpretty
        httpretty.enable()
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        json_response = ('[[2191833, "Haute Cime", null], '
                         '[2433141, "Grammont", null], '
                         '[2692136, "Rochers de Nayes", null], '
                         '[3011765, "Villeneuve - Leysin", null]]')

        httpretty.register_uri(
            httpretty.GET, routes_list_url,
            content_type="application/json", body=json_response,
            status=200
        )

        # intercept getmeta call to map.wandland.ch with httpretty
        # remove "https://
        route_meta_url = settings.SWITZERLAND_MOBILITY_META_URL[8:]
        # Turn the route meta URL into a regular expression
        route_meta_url = re.compile(route_meta_url.replace('%d', '(\w+)'))

        route_json = (
            '{"length": 12345.6,'
            '"totalup": 1234.5,'
            '"totaldown": 4321.0}'
        )

        httpretty.register_uri(
            httpretty.GET, route_meta_url,
            content_type="application/json", body=route_json,
            status=200
        )

        new_routes, old_routes, response = SwitzerlandMobilityRoute.objects.\
            get_remote_routes(session, user)
        httpretty.disable()

        self.assertEqual(len(new_routes), 3)
        self.assertEqual(len(old_routes), 1)
        self.assertEqual(response['error'], False)
        # self.assertEqual(new_routes[1]['length'].m, 12345.6)

    def test_get_raw_route_details_success(self):
        route_id = 2191833

        # intercept routes_list call to map.wandland.ch with httpretty
        httpretty.enable()
        route_url = settings.SWITZERLAND_MOBILITY_ROUTE_URL % route_id

        route_details_json = self.route_details_json

        httpretty.register_uri(
            httpretty.GET, route_url,
            content_type="application/json", body=route_details_json,
            status=200
        )

        route_raw_json, response = SwitzerlandMobilityRoute.objects.\
            get_raw_route_details(route_id)

        httpretty.disable()

        self.assertEqual('Leuk Bridge', route_raw_json['properties']['name'])
        self.assertEqual(response['error'], False)

    def test_get_raw_route_details_error(self):
        route_id = 9999999

        # intercept routes_list call to map.wandland.ch with httpretty
        httpretty.enable()
        route_url = settings.SWITZERLAND_MOBILITY_ROUTE_URL % route_id

        html_response = self.html_404

        httpretty.register_uri(
            httpretty.GET, route_url,
            content_type="text/html", body=html_response,
            status=404
        )

        route_raw_json, response = SwitzerlandMobilityRoute.objects.\
            get_raw_route_details(route_id)

        httpretty.disable()

        self.assertEqual(False, route_raw_json)
        self.assertEqual(response['error'], True)
        self.assertTrue('404' in response['message'])

    def test_already_imported(self):
        route = SwitzerlandMobilityRoute(**self.route_data)
        self.assertEqual(route.already_imported(), False)
        route.save()
        self.assertEqual(route.already_imported(), True)

    #########
    # Views #
    #########

    def test_switzerland_mobility_detail_success(self):
        route_id = 2823968
        url = reverse('switzerland_mobility_detail', args=[route_id])

        # intercept call to Switzerland Mobility with httpretty
        httpretty.enable()
        details_json_url = settings.SWITZERLAND_MOBILITY_ROUTE_URL % route_id
        json_response = self.route_details_json

        httpretty.register_uri(
            httpretty.GET, details_json_url,
            content_type="application/json", body=json_response,
            status=200
        )

        response = self.client.get(url)

        httpretty.disable()

        title = '<title>Home by Two - Import Leuk Bridge</title>'
        start_place_form = (
            '<select id="id_route-start_place" '
            'name="route-start_place">'
        )
        places_formset = (
            '<input id="id_places-TOTAL_FORMS" '
            'name="places-TOTAL_FORMS" type="hidden" value="0" />'
        )

        map_data = '<div id="main" class="leaflet-container-default"></div>'

        self.assertEqual(response.status_code, 200)
        self.assertTrue(title in str(response.content))
        self.assertTrue(start_place_form in str(response.content))
        self.assertTrue(places_formset in str(response.content))
        self.assertTrue(map_data in str(response.content))

    def test_switzerland_mobility_detail_already_imported(self):
        route = SwitzerlandMobilityRoute(**self.route_data)
        route.save()

        route_id = 2191833
        url = reverse('switzerland_mobility_detail', args=[route_id])
        content = 'Already Imported'

        # intercept call to Switzerland Mobility with httpretty
        httpretty.enable()
        details_json_url = settings.SWITZERLAND_MOBILITY_ROUTE_URL % route_id
        json_response = self.route_details_json

        httpretty.register_uri(
            httpretty.GET, details_json_url,
            content_type="application/json", body=json_response,
            status=200
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(content in str(response.content))

    def test_switzerland_mobility_detail_server_error(self):
        route_id = 999999999999
        url = reverse('switzerland_mobility_detail', args=[route_id])
        content = 'Error 500'

        # intercept call to Switzerland Mobility with httpretty
        httpretty.enable()
        details_json_url = settings.SWITZERLAND_MOBILITY_ROUTE_URL % route_id
        html_response = self.html_500

        httpretty.register_uri(
            httpretty.GET, details_json_url,
            content_type="text/html", body=html_response,
            status=500
        )

        response = self.client.get(url)

        httpretty.disable()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(content in str(response.content))

    def test_switzerland_mobility_detail_post_success_no_places(self):
        route_id = 2191833
        post_data = {
            'route-'+key: value
            for key, value in self.route_data.items()
        }

        post_data.update({
            'route-start_place': Place.objects.get(name='Start_Place').id,
            'route-end_place': Place.objects.get(name='End_Place').id,
            'places-TOTAL_FORMS': 0,
            'places-INITIAL_FORMS': 0,
            'places-MIN_NUM_FORMS': 0,
            'places-MAX_NUM_FORMS': 1000,
        })

        url = reverse('switzerland_mobility_detail', args=[route_id])
        response = self.client.post(url, post_data)

        route = SwitzerlandMobilityRoute.objects.get(source_id=route_id)
        redirect_url = reverse('routes:detail', args=[route.id])

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_switzerland_mobility_detail_post_success_place(self):
        route_id = 2191833
        post_data = {
            'route-'+key: value
            for key, value in self.route_data.items()
        }

        start_place = Place.objects.get(name='Start_Place')
        end_place = Place.objects.get(name='End_Place')

        post_data.update({
            'route-start_place': start_place.id,
            'route-end_place': end_place.id,
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

        url = reverse('switzerland_mobility_detail', args=[route_id])
        response = self.client.post(url, post_data)

        # a new route has been created
        route = SwitzerlandMobilityRoute.objects.get(source_id=route_id)
        route_places = RoutePlace.objects.filter(route=route.id)
        self.assertEqual(route_places.count(), 2)

        redirect_url = reverse('routes:detail', args=[route.id])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_switzerland_mobility_detail_post_no_validation_places(self):
        route_id = 2191833
        post_data = {
            'route-'+key: value
            for key, value in self.route_data.items()
        }

        start_place = Place.objects.get(name='Start_Place')
        end_place = Place.objects.get(name='End_Place')

        post_data.update({
            'route-start_place': start_place.id,
            'route-end_place': end_place.id,
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

        url = reverse('switzerland_mobility_detail', args=[route_id])
        response = self.client.post(url, post_data)
        alert_box = '<div class="box alert alert--error">'
        required_field = 'This field is required.'
        not_a_number = 'Enter a number.'

        self.assertEqual(response.status_code, 200)
        self.assertTrue(alert_box in str(response.content))
        self.assertTrue(required_field in str(response.content))
        self.assertTrue(not_a_number in str(response.content))

    def test_switzerland_mobility_detail_post_integrity_error(self):

        route = SwitzerlandMobilityRoute(**self.route_data)
        route.save()

        route_id = 2191833
        post_data = {
            'route-'+key: value
            for key, value in self.route_data.items()
        }

        start_place = Place.objects.get(name='Start_Place')
        end_place = Place.objects.get(name='End_Place')

        post_data.update({
            'route-start_place': start_place.id,
            'route-end_place': end_place.id,
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

        url = reverse('switzerland_mobility_detail', args=[route_id])
        response = self.client.post(url, post_data)

        alert_box = '<div class="box alert alert--error">'
        integrity_error = (
            'Integrity Error: duplicate key value violates unique constraint'
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(alert_box in str(response.content))
        self.assertTrue(integrity_error in str(response.content))

    def test_switzerland_mobility_index_success(self):
        url = reverse('switzerland_mobility_index')
        content = '<h1>Import Routes from Switzerland Mobility Plus</h1>'
        self.add_cookies_to_session()

        # intercept call to map.wanderland.ch
        httpretty.enable()
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        json_response = ('[[2191833, "Haute Cime", null], '
                         '[2433141, "Grammont", null], '
                         '[2692136, "Rochers de Nayes", null], '
                         '[3011765, "Villeneuve - Leysin", null]]')

        httpretty.register_uri(
            httpretty.GET, routes_list_url,
            content_type="application/json", body=json_response,
            status=200
        )

        response = self.client.get(url)

        httpretty.disable()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(content in str(response.content))

    def test_switzerland_mobility_index_error(self):
        url = reverse('switzerland_mobility_index')
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

        httpretty.disable()

        content = ('Error 500: could not retrieve information from %s. '
                   % routes_list_url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(content in str(response.content))

    def test_switzerland_mobility_index_no_cookies(self):
        url = reverse('switzerland_mobility_index')
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
        self.assertEqual(response.url, reverse('switzerland_mobility_index'))
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
        start_place = Place.objects.get(name='Start_Place')
        end_place = Place.objects.get(name='End_Place')

        places = {
            'start_place': start_place.id,
            'end_place': end_place.id,
        }

        route_data = self.route_data
        route_data.update(places)

        form = SwitzerlandMobilityRouteForm(data=route_data)
        self.assertTrue(form.is_valid())

    def test_switzerland_mobility_invalid_model_form(self):
        data = self.route_data
        del data['geom']
        form = SwitzerlandMobilityRouteForm(data=data)
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
        dir_path = os.path.dirname(os.path.realpath(__file__))

        if file_type == 'shp':
            # Test file with 35 features only
            shapefile = os.path.join(
                dir_path,
                'data',
                'TestSwissNAMES3D_PKT.shp'
            )
            return shapefile

        else:
            # Bad empty data
            text_data = os.path.join(dir_path, 'data', 'text.txt')
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