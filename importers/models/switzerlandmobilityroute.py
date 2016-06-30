from __future__ import unicode_literals

from django.conf import settings

from django.contrib.gis.db import models
from django.contrib.gis.measure import Distance
from django.contrib.gis.geos import LineString, GEOSGeometry

import googlemaps
import requests
import json
import sys


class SwitzerlandMobilityRouteManager(models.Manager):

    # login to Switzerland Mobility and retrieve route list
    def get_routes_list_from_server(self, credentials):
        login_url = 'https://map.wanderland.ch/user/login'

        # login to map.wanderland.ch
        r = requests.post(login_url, data=json.dumps(credentials))

        # save cookies
        if r.status_code == requests.codes.ok:
            cookies = r.cookies
        else:
            sys.exit("Error: could not log-in to map.wanderland.ch")

        # retrieve route list
        routes_list_url = 'https://map.wanderland.ch/tracks_list'

        r = requests.post(routes_list_url, cookies=cookies)

        if r.status_code == requests.codes.ok:
            routes = r.json()
        else:
            sys.exit(
                "Error: could not retrieve routes list from map.wanderland.ch"
            )

        # Take routes list returned by map.wanderland.ch as list of 3 values
        # e.g. [2692136, u'Rochers de Nayes', None] and add dictionnary labels
        formatted_routes = []

        for route in routes:
            formatted_route = {
                'id': route[0],
                'name': route[1],
                'description': route[2]
            }

            formatted_routes.append(formatted_route)

            # update routes list in the database
            routes = SwitzerlandMobilityRoute.objects
            switzerland_mobility_route, created = routes.get_or_create(
                    switzerland_mobility_id=formatted_route['id'],
                    defaults={
                            'name': formatted_route['name'],
                            'totalup': 0,
                            'totaldown': 0,
                            'length': 0,
                            'geom': LineString((0, 0), (0, 0)),
                            'description': formatted_route['description']
                        }

                )

            # update route name if it has changed
            if (
                not(created) and
                switzerland_mobility_route.name != formatted_route['name']
            ):
                switzerland_mobility_route.name = formatted_route['name']
                switzerland_mobility_route.save()

        return formatted_routes


class SwitzerlandMobilityRoute(models.Model):
    switzerland_mobility_id = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=50)
    description = models.TextField('Text description of the Route', default='')

    # elevation gain in m
    totalup = models.FloatField('Total elevation gain in m', default=0)
    # elevation loss in m
    totaldown = models.FloatField('Total elevation loss in m', default=0)
    # route distance in m
    length = models.FloatField('Total length of the track in m', default=0)

    # creation and update date
    updated = models.DateTimeField('Time of last update', auto_now=True)
    created = models.DateTimeField('Time of creation', auto_now_add=True)
    owner = models.BigIntegerField('Switzerland Mobility User ID')

    # geographic information
    geom = models.LineStringField('line geometry', srid=21781)
    altitude = models.TextField('Altitude information as JSON', default='')

    objects = SwitzerlandMobilityRouteManager()

    # retrieve map.wanderland.ch route information
    def get_routes_details_from_server(self):

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

    def get_distance(self, unit='m'):
        return Distance(**{unit: self.length})

    def get_point_elevation(self, location=0):
        point = self.geom.interpolate_normalized(location)
        point.transform(4326)
        coords = (point.y, point.x)

        gmaps = googlemaps.Client(key=settings.GOOGLEMAPS_API_KEY)
        result = gmaps.elevation(coords)

        return result[0]['elevation']

    # Returns the string representation of the model.
    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.name
