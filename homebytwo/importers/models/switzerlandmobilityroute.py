import json

from requests import get, codes
from requests.exceptions import ConnectionError
from ast import literal_eval
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.measure import Distance
from pandas import DataFrame

from ...routes.models import Route, RouteManager
from ..utils import SwitzerlandMobilityError


def request_json(url, cookies=None):
    """
    Makes get call the map.wanderland.ch website and retrieves a json
    while managing server and connection errors.
    """
    try:
        r = get(url, cookies=cookies)

    # connection error and inform the user
    except ConnectionError as e:
        message = "Connection Error: could not connect to {0}. "
        raise ConnectionError(message.format(url))

    else:
        # if request is successful save json object
        if r.status_code == codes.ok:
            json = r.json()
            return json

        # server error: display the status code
        else:
            message = "Error {0}: could not retrieve information from {1}"
            raise SwitzerlandMobilityError(message.format(r.status_code, url))


class SwitzerlandMobilityRouteManager(RouteManager):
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

    def get_remote_routes(self, session, user):
        """
        Use the authorization cookies saved in the session
        to return the user's raw route list as json and format
        them for display
        """
        cookies = session['switzerland_mobility_cookies']

        # retrieve route list
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        raw_routes = request_json(routes_list_url, cookies)

        # could retrieve route list successfully
        if raw_routes:

            # format routes into dictionary
            formatted_routes = self.format_raw_remote_routes(raw_routes)

            # split into old and new routes
            new_routes, old_routes = self.check_for_existing_routes(
                owner=user,
                routes=formatted_routes,
                data_source='switzerland_mobility',
            )

            return new_routes, old_routes

        # return two empty lits if no raw_routes were found
        else:
            return [], []

    def format_raw_remote_routes(self, raw_routes):
        """
        Take routes list returned by Switzerland Mobility as list of 3 values
        e.g. [2692136, u'Rochers de Nayes', None] and create a new
        dictionnary list with id, name and description
        """
        formatted_routes = []

        # Iterate through json object
        for route in raw_routes:
            formatted_route = SwitzerlandMobilityRoute(
                source_id=route[0],
                name=route[1],
                description=route[2],
            )

            # If description is None convert it to empty
            if formatted_route.description is None:
                formatted_route.description = ''

            formatted_routes.append(formatted_route)

        return formatted_routes


class SwitzerlandMobilityRoute(Route):

    """
    Proxy for Route Model with specific methods and custom manager.
    """

    class Meta:
        proxy = True

    # Custom manager
    objects = SwitzerlandMobilityRouteManager()

    def get_route_details(self):
        """
        Fetches route details from map.wanderland.ch.
        """

        # Create the URL
        route_url = settings.SWITZERLAND_MOBILITY_ROUTE_URL % self.source_id

        # request from Switzerland Mobility
        raw_route_json = request_json(route_url)

        # if response is a success, format the route info
        if raw_route_json:
            self.format_raw_route_details(raw_route_json)

    def format_raw_route_details(self, raw_route_json):
        """
        Converts the json returned by Switzerland mobility
        into an instance of the SwitzerlandMobilityRoute model.
        """

        self.name = raw_route_json['properties']['name']
        self.length = raw_route_json['properties']['meta']['length']
        self.totalup = raw_route_json['properties']['meta']['totalup']
        self.totaldown = raw_route_json['properties']['meta']['totaldown']

        # Add Swiss Coordinate System Information to the JSON
        crs = {
            "type": "name",
            "properties": {
                "name": "epsg:21781"
            }
        }

        raw_route_json['geometry']['crs'] = crs

        # create geom from GeoJSON
        self.geom = GEOSGeometry(
            json.dumps(raw_route_json['geometry']),
            srid=21781)

        # save profile data to pandas DataFrame
        self.data = DataFrame(
            literal_eval(raw_route_json['properties']['profile']),
            columns=['lat', 'lng', 'altitude', 'length'])

        # compute elevation data
        self.calculate_cummulative_elevation_differences()

    def add_route_remote_meta(self):
        """
        Gets a route's meta information from map.wanderland.ch
        and ads them to an existing route json.

        Example response:
        {"length": 6047.5,
        "totalup": 214.3,
        "totaldown": 48.7,
        ...}
        """
        meta_url = settings.SWITZERLAND_MOBILITY_META_URL % self.source_id

        # request metadata
        route_meta_json = request_json(meta_url)

        if route_meta_json:
            # save as distance objetcs for easy conversion, e.g. length.mi
            self.length = Distance(m=route_meta_json['length'])
            self.totalup = Distance(m=route_meta_json['totalup'])
            self.totaldown = Distance(m=route_meta_json['totaldown'])

        # In case of error, return the original route and explain the error.
        else:
            message = "Could not retrieve meta-information for route: '{}'."
            raise ConnectionError(message.format(self.name))

    def save(self, *args, **kwargs):
        """
        Set the data_source of the route to switzerland_mobility
        when saving the route.
        """
        # set the data_source of the route to switzerland_mobility
        self.data_source = 'switzerland_mobility'

        # Save with the parent method
        super(SwitzerlandMobilityRoute, self).save(*args, **kwargs)
