import json
from ast import literal_eval

from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry

from pandas import DataFrame

from ...routes.models import Route, RouteManager
from ...routes.utils import Link
from ..exceptions import SwitzerlandMobilityMissingCredentials
from ..utils import request_json


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
        them for display.
        """
        cookies = session["switzerland_mobility_cookies"]

        # retrieve route list
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        raw_routes = request_json(routes_list_url, cookies)

        # could retrieve route list successfully
        if raw_routes:

            # format routes into dictionary
            return self._format_raw_remote_routes(raw_routes, athlete)

        # return empty list if no raw_routes were found
        else:
            return []

    def _format_raw_remote_routes(self, raw_routes, athlete):
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

    def check_user_credentials(self, request):
        """
        view function provided to check whether a user has access
        to Switzerland Mobility Plus before call the service.
        """
        # Check if logged-in to Switzeland Mobility
        try:
            request.session["switzerland_mobility_cookies"]

        # login cookies missing
        except KeyError:
            raise SwitzerlandMobilityMissingCredentials


class SwitzerlandMobilityRoute(Route):

    """
    Proxy for Route Model with specific methods and custom manager.
    """

    # data source name to display in templates
    DATA_SOURCE_NAME = "Switzerland Mobility Plus"
    DATA_SOURCE_LINK = Link(
        "https://map.schweizmobil.ch/?lang=en&showLogin=true", DATA_SOURCE_NAME,
    )

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

        # calculate schedule for route owner
        self.calculate_projected_time_schedule(self.athlete.user)

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
