from __future__ import unicode_literals

from django.conf import settings
from django.contrib.gis.db import models
from routes.models import Route
from django.contrib.gis.geos import GEOSGeometry

import requests
import json
import sys


class SwitzerlandMobilityRouteManager(models.Manager):

    """
    Mainly used to retrieve route infos from the server
    """

    def get_remote_routes(self, session, user):
        raw_routes, response = self.get_raw_remote_routes(session)

        # could retrieve route list successfully
        if not response['error']:

            # format routes into dictionary
            formatted_routes = self.format_raw_remote_routes(raw_routes)

            # split into old and new routes
            new_routes, old_routes = self.check_for_existing_routes(
                formatted_routes, user)

            return new_routes, old_routes, response

        # there was an error retrieving the user's route list
        else:

            return False, False, response

    def get_raw_remote_routes(self, session):
        """
        Use the authorization cookies saved in the session
        to return a tuple with user's raw route list as json
        and the request status.
        """
        cookies = session['switzerland_mobility_cookies']

        # retrieve route list
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        r = requests.get(routes_list_url, cookies=cookies)

        # if request succeeds save json object
        if r.status_code == requests.codes.ok:
            raw_routes = r.json()
            response = {'error': False, 'message': 'OK'}

            return raw_routes, response

        else:
            message = ("Error %d: could not retrieve your routes list "
                       "from map.wanderland.ch" % r.status_code)
            response = {'error': True, 'message': message}

            return False, response

    def format_raw_remote_routes(self, raw_routes):
        """
        Take routes list returned by map.wanderland.ch as list of 3 values
        e.g. [2692136, u'Rochers de Nayes', None] and create a new
        dictionnary list with id, name and description
        """
        formatted_routes = []

        # Iterate through json object
        for route in raw_routes:
            formatted_route = {
                'id': route[0],
                'name': route[1],
                'description': route[2],
            }

            # If description is None convert it to empty
            if formatted_route['description'] is None:
                formatted_route['description'] = ''

            formatted_routes.append(formatted_route)

        return formatted_routes

    def check_for_existing_routes(self, formatted_routes, user):
        """
        Split remote routes into old and new routes.
        Old routes have already been imported by the user.
        New routes have not been imported yet.
        """
        new_routes = []
        old_routes = []

        for route in formatted_routes:
            user_routes = self.filter(user=user)
            if user_routes.filter(switzerland_mobility_id=route['id']).exists():
                old_routes.append(route)
            else:
                new_routes.append(route)

        return new_routes, old_routes


class SwitzerlandMobilityRoute(Route):

    """
    Extends Route class with specific attributes and methods
    """

    switzerland_mobility_id = models.BigIntegerField(unique=True)

    # geographic information
    altitude = models.TextField('Altitude information as JSON', default='')

    objects = SwitzerlandMobilityRouteManager()

    def get_route_details_from_server(self):
        """ retrieve map.wanderland.ch detail information for a route """

        route_id = self.switzerland_mobility_id
        route_url = 'https://map.wanderland.ch/track/%d/show' % route_id

        r = requests.get(route_url)

        if r.status_code == requests.codes.ok:
            route_json = r.json()
        else:
            sys.exit(
                "Error: could not retrieve route information "
                "from map.wanderland.ch for route " + route_id
            )

        # Add route information
        self.totalup = route_json['properties']['meta']['totalup']
        self.totaldown = route_json['properties']['meta']['totaldown']
        self.length = route_json['properties']['meta']['length']

        # Add GeoJSON line linestring from profile information in json
        polyline = {}

        # Set geometry type to LineString
        polyline['type'] = 'LineString'

        coordinates = []

        for point in json.loads(route_json['properties']['profile']):
            position = [point[0], point[1]]
            coordinates.append(position)

        polyline['coordinates'] = coordinates

        self.geom = GEOSGeometry(json.dumps(polyline), srid=21781)

        # Record altitude infromation to a list as long as the LineString
        altitude = []

        for point in json.loads(route_json['properties']['profile']):
            altitude.append(point[2])

        self.altitude = json.dumps(altitude)

        # Save to database
        self.save()

        return self
