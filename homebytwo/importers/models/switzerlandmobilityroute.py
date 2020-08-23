from ast import literal_eval

from django.conf import settings
from django.contrib.gis.geos import LineString

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
        try:
            cookies = session["switzerland_mobility_cookies"]

        # login cookies missing
        except KeyError:
            message = "Please connect to Switzerland Mobility, first."
            raise SwitzerlandMobilityMissingCredentials(message)

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
                source_id=route["id"],
                name=route["name"],
                description="",
                athlete=athlete,
            )

            formatted_routes.append(formatted_route)

        return formatted_routes


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

    def get_route_details(self, cookies):
        """
        fetch route details from map.wanderland.ch.

        Routes that are not shared publicly on Switzerland mobility
        can only be accessed by their owner. We try to pass the authorization
        cookies of the user to access his private routes.
        """
        route_url = settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL % self.source_id

        # request route details from Switzerland Mobility
        raw_route_json = request_json(route_url, cookies)

        # if response is a success, format the route info
        if raw_route_json:

            # set route name
            self.name = raw_route_json["properties"]["name"]

            # use Switzerland Mobility values until we calculate them from data
            self.total_distance = raw_route_json["properties"]["meta"]["length"]
            self.total_elevation_gain = raw_route_json["properties"]["meta"]["totalup"]
            self.total_elevation_loss = raw_route_json["properties"]["meta"][
                "totaldown"
            ]

            # save route profile as DataFrame
            self.data = DataFrame(
                literal_eval(raw_route_json["properties"]["profile"]),
                columns=["lat", "lng", "altitude", "distance"],
            )

            # create geom from lat, lng data columns
            coords = [
                (lat, lng) for lat, lng in zip(self.data["lat"], self.data["lng"])
            ]
            self.geom = LineString(coords, srid=21781)

            # remove redundant lat, lng columns in data
            self.data.drop(columns=["lat", "lng"], inplace=True)
