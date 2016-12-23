from __future__ import unicode_literals

from django.conf import settings
from django.contrib.gis.db import models
from routes.models import Route
from django.contrib.gis.geos import LineString, GEOSGeometry

import requests
import json
import sys


class SwitzerlandMobilityRouteManager(models.Manager):

    """
    login to Switzerland Mobility and retrieve route list.
    Takes the user from the request object.
    """

    def get_routes_list_from_server(self, user):

        cookies = user.cookies

        # retrieve route list
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL

        r = requests.post(routes_list_url, cookies=cookies)

        # if request succeeds save json object
        if r.status_code == requests.codes.ok:
            routes = r.json()
        else:
            sys.exit(
                "Error: could not retrieve routes list from map.wanderland.ch"
            )

        # Take routes list returned by map.wanderland.ch as list of 3 values
        # e.g. [2692136, u'Rochers de Nayes', None] and create a new
        # dictionnary list with id, name and description
        formatted_routes = []

        # Iterate through json object
        for route in routes:
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

    def save_all_routes_to_database(self, user):

        formatted_routes = self.get_routes_list_from_server()

        for route in formatted_routes:

            # update routes list in the database
            objects = SwitzerlandMobilityRoute.objects
            switzerland_mobility_route, created = objects.get_or_create(
                    switzerland_mobility_id=route['id'],
                    defaults={
                            'name': route['name'],
                            'totalup': 0,
                            'totaldown': 0,
                            'length': 0,
                            'geom': LineString((0, 0), (0, 0)),
                            'description': route['description'],
                            'switzerland_mobility_owner': 0,
                            'user': user,
                        }

                )

            # update route name if it has changed
            if (
                not(created) and
                switzerland_mobility_route.name != route['name']
            ):
                switzerland_mobility_route.name = route['name']
                switzerland_mobility_route.save()


class SwitzerlandMobilityRoute(Route):

    """
    Extends Route class with specific attributes and methods
    """

    switzerland_mobility_id = models.BigIntegerField(unique=True)
    switzerland_mobility_owner = models.BigIntegerField('Wanderland user ID')

    # geographic information
    altitude = models.TextField('Altitude information as JSON', default='')

    objects = SwitzerlandMobilityRouteManager()

    def get_route_details_from_server(self):
        """ retrieve map.wanderland.ch detail information for a route """

        route_base_url = 'https://map.wanderland.ch/track/'
        route_id = str(self.switzerland_mobility_id)
        route_url = route_base_url + route_id + "/show"

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
        self.owner = route_json['properties']['owner']

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
