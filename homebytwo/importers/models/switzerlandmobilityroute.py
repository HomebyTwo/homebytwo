import json
from ast import literal_eval

from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.measure import Distance

from pandas import DataFrame
from requests.exceptions import ConnectionError

from ...routes.models import Route, RouteManager
from ..utils import request_json, split_in_new_and_existing_routes


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
        return super().get_queryset().filter(data_source="switzerland_mobility")

    def get_remote_routes_list(self, session, athlete):
        """
        Use the authorization cookies saved in the session
        to return the athlete's raw route list as json and format
        them for display
        """
        cookies = session["switzerland_mobility_cookies"]

        # retrieve route list
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        raw_routes = request_json(routes_list_url, cookies)

        # could retrieve route list successfully
        if raw_routes:

            # format routes into dictionary
            formatted_routes = self.format_raw_remote_routes(raw_routes, athlete)

            # split routes in two  lists: into old and new routes
            return split_in_new_and_existing_routes(formatted_routes)

        # return two empty lits if no raw_routes were found
        else:
            return [], []

    def format_raw_remote_routes(self, raw_routes, athlete):
        """
        Take routes list returned by Switzerland Mobility as list of 3 values
        e.g. [2692136, u'Rochers de Nayes', None] and create a new
        dictionnary list with id, name and description
        """
        formatted_routes = []

        # Iterate through json object and create stubs
        for route in raw_routes:
            formatted_route = SwitzerlandMobilityRoute(
                source_id=route[0],
                name=route[1],
                description=route[2],
                athlete=athlete,
            )

            # If description is None convert it to empty
            if formatted_route.description is None:
                formatted_route.description = ""

            formatted_routes.append(formatted_route)

        return formatted_routes


class SwitzerlandMobilityRoute(Route):

    """
    Proxy for Route Model with specific methods and custom manager.
    """

    def __init__(self, *args, **kwargs):
        """
        Set the data_source of the route to Switzerland Mobility
        when instatiatind a route.
        """
        super().__init__(*args, **kwargs)
        self.data_source = "switzerland_mobility"

    class Meta:
        proxy = True

    # Custom manager
    objects = SwitzerlandMobilityRouteManager()

    def get_route_details(self):
        """
        Fetches route details from map.wanderland.ch.
        """
        route_url = settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL % self.source_id

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
        self.name = raw_route_json["properties"]["name"]
        self.length = raw_route_json["properties"]["meta"]["length"]
        self.totalup = raw_route_json["properties"]["meta"]["totalup"]
        self.totaldown = raw_route_json["properties"]["meta"]["totaldown"]

        # Add Swiss Coordinate System Information to the JSON
        crs = {"type": "name", "properties": {"name": "epsg:21781"}}

        raw_route_json["geometry"]["crs"] = crs

        # create geom from GeoJSON
        self.geom = GEOSGeometry(json.dumps(raw_route_json["geometry"]), srid=21781)

        # save profile data to pandas DataFrame
        self.data = DataFrame(
            literal_eval(raw_route_json["properties"]["profile"]),
            columns=["lat", "lng", "altitude", "length"],
        )

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
            self.length = Distance(m=route_meta_json["length"])
            self.totalup = Distance(m=route_meta_json["totalup"])
            self.totaldown = Distance(m=route_meta_json["totaldown"])

        # In case of error, return the original route and explain the error.
        else:
            message = "Could not retrieve meta-information for route: '{}'."
            raise ConnectionError(message.format(self.name))
