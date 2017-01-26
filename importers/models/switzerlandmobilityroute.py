from __future__ import unicode_literals

from django.conf import settings
from django.contrib.gis.db import models
from routes.models import Route
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.measure import Distance

import requests
import json


class SwitzerlandMobilityRouteManager(models.Manager):

    """
    Custom manager used to retrieve data from Switzerland Mobility
    """

    def get_queryset(self):
        """
        Returns query_sets with Switzerland Mobility Routes only.
        This method is required because SwitzerlandMobilityRoute
        is a proxy class.
        """
        return super(SwitzerlandMobilityRouteManager, self). \
            get_queryset().filter(data_source='switzerland_mobility')

    def request_json(self, url, cookies=None):
        """
        Makes get call the map.wanderland.ch website and retrieves a json
        while managing server and connection errors.
        """
        try:
            r = requests.get(url, cookies=cookies)

            # if request is successful save json object
            if r.status_code == requests.codes.ok:
                json = r.json()
                response = {'error': False, 'message': 'OK. '}

                return json, response

            # server error: display the status code
            else:
                message = ("Error %d: could not retrieve information from %s. "
                           % (r.status_code, url))
                response = {'error': True, 'message': message}

                return False, response

        # connection error and inform the user
        except requests.exceptions.ConnectionError:
            message = "Connection Error: could not connect to %s. " % url
            response = {'error': True, 'message': message}

            return False, response

    def get_remote_routes(self, session, user):
        """
        This is the main workflow method to retrieve routes for a user
        on Switzerland Mobility plus.
        It requires the session with cookies (checked in the view)
        """
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
        to return the user's raw route list as json.
        """
        cookies = session['switzerland_mobility_cookies']

        # retrieve route list
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        raw_routes, response = self.request_json(routes_list_url, cookies)

        return raw_routes, response

    def format_raw_remote_routes(self, raw_routes):
        """
        Take routes list returned by Switzerland Mobility as list of 3 values
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
            route_id = route['id']
            user_routes = self.filter(user=user)
            if user_routes.filter(source_id=route_id).exists():
                old_routes.append(route)
            else:
                new_routes.append(route)

        return new_routes, old_routes

    def add_route_remote_meta(self, route):
        """
        Gets a route's meta information from map.wanderland.ch
        and ads them to an existing route json.

        Example response:
        {"length": 6047.5,
        "totalup": 214.3,
        "totaldown": 48.7,
        ...}
        """
        route_id = route['id']
        meta_url = settings.SWITZERLAND_MOBILITY_META_URL % route_id

        # request metadata
        route_meta_json, route_response = self.request_json(meta_url)

        if not route_response['error']:
            # save as distance objetcs for easy conversion, e.g. length.mi
            length = Distance(m=route_meta_json['length'])
            totalup = Distance(m=route_meta_json['totalup'])
            totaldown = Distance(m=route_meta_json['totaldown'])

            route_meta = {
                'totalup': totalup,
                'totaldown': totaldown,
                'length': length,
            }

            # Update the route with meta information collected
            route.update(route_meta)

            error = route_response['error']
            message = route_response['message']

        # In case of error, return the original route and explain the error.
        else:
            error = True
            message = ("Error: could not retrieve meta-information "
                       "for route: '%s'. " % (route['name']))

        return route, {'error': error, 'message': message}

    def get_remote_route(self, source_id):
        """
        Workflow method to retrieve route details from Switzerland Mobility.
        Return an Instance of the SwitzerlandMobilityRoute model
        and the response status.
        """

        # retrieve the json details from the remote server
        raw_route_json, response = self.get_raw_route_details(source_id)

        # if response is a success, format the route info
        if not response['error']:
            formatted_route = self.format_raw_route_details(raw_route_json)

        else:
            formatted_route = False

        return formatted_route, response

    def get_raw_route_details(self, source_id):
        """
        Fetches route details from map.wanderland.ch.
        The retuned json has the following structure:

        """
        # Create the URL
        route_id = source_id
        route_url = settings.SWITZERLAND_MOBILITY_ROUTE_URL % route_id

        # request from Switzerland Mobility
        route_raw_json, response = self.request_json(route_url)

        return route_raw_json, response

    def format_raw_route_details(self, raw_route_json):
        """
        Converts the json returned by Switzerland mobility
        into an instance of the SwitzerlandMobilityRoute model.
        """

        # Route name
        route_id = raw_route_json['id']
        name = raw_route_json['properties']['name']
        length = raw_route_json['properties']['meta']['length']
        totalup = raw_route_json['properties']['meta']['totalup']
        totaldown = raw_route_json['properties']['meta']['totaldown']
        geometry = raw_route_json['geometry']

        formatted_route = SwitzerlandMobilityRoute(
            source_id=route_id,
            name=name,
            length=length,
            totalup=totalup,
            totaldown=totaldown,
            # load GeoJSON using GEOSGeeometry
            geom=GEOSGeometry(json.dumps(geometry), srid=21781)
        )

        return formatted_route


class SwitzerlandMobilityRoute(Route):

    """
    Proxy for Route Model with specific methods and custom manager.
    """

    class Meta:
        proxy = True

    # Custom manager
    objects = SwitzerlandMobilityRouteManager()

    def already_imported(self):
        """
        check if route has already been imported to the database
        """
        imported_route = SwitzerlandMobilityRoute.objects. \
            filter(source_id=self.source_id, user=self.user)

        return imported_route.exists()

    def save(self, *args, **kwargs):
        """
        Set the data_source of the route to switzerland_mobility
        when saving the route.
        """
        # set the data_source of the route to switzerland_mobility
        self.data_source = 'switzerland_mobility'

        # Save with the parent method
        super(SwitzerlandMobilityRoute, self).save(*args, **kwargs)
