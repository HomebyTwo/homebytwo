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

    @staticmethod
    def get_remote_routes_list(athlete, cookies=None):
        """
        Use the authorization cookies saved in the session
        to return the athlete's list of routes on Switzerland Mobility
        e.g. [2692136, u'Rochers de Nayes', None] as a list of
        SwitzerlandMobilityRoute objects routes.
        """
        if cookies is None:
            message = "Please connect to Switzerland Mobility, first."
            raise SwitzerlandMobilityMissingCredentials(message)

        # retrieve route list
        routes_list_url = settings.SWITZERLAND_MOBILITY_LIST_URL
        raw_routes = request_json(routes_list_url, cookies)

        if raw_routes:
            # return list of SwitzerlandMobility objects
            return [
                SwitzerlandMobilityRoute(
                    source_id=route["id"],
                    name=route["name"],
                    description="",
                    athlete=athlete,
                )
                for route in raw_routes
            ]

        # return empty list if no routes were found
        else:
            return []


class SwitzerlandMobilityRoute(Route):

    """
    Proxy for Route Model with specific methods and custom manager.
    """

    # data source name to display in templates
    DATA_SOURCE_NAME = "Switzerland Mobility Plus"
    DATA_SOURCE_LINK = Link(
        "https://map.schweizmobil.ch/?lang=en&showLogin=true",
        DATA_SOURCE_NAME,
    )

    # Custom manager
    objects = SwitzerlandMobilityRouteManager()

    class Meta:
        proxy = True

    def __init__(self, *args, **kwargs):
        """
        Set the data_source of the route to Switzerland Mobility
        when instantiating a route.
        """
        super().__init__(*args, **kwargs)
        self.data_source = "switzerland_mobility"

    @property
    def route_data_url(self):
        return settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL % self.source_id

    def get_route_details(self, cookies=None):
        """
        fetch route details from map.wanderland.ch.

        Routes that are not shared publicly on Switzerland mobility
        can only be accessed by their owner. We try to pass the authorization
        cookies of the user to access his private routes.
        """

        # request route details from Switzerland Mobility
        raw_route_json = request_json(self.route_data_url, cookies)

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
            self.geom, self.data = self.get_route_data(raw_route_json=raw_route_json)

    def get_route_data(self, cookies=None, raw_route_json=None):
        """
        convert raw json into the route geom and a pandas DataFrame
        with columns for distance and altitude.
        """
        if not raw_route_json:
            # request route details from Switzerland Mobility
            raw_route_json = request_json(self.route_data_url, cookies)

        if raw_route_json:
            data = DataFrame(
                literal_eval(raw_route_json["properties"]["profile"]),
                columns=["lat", "lng", "altitude", "distance"],
            )

            # create geom from lat, lng data columns
            coords = list(zip(data["lat"], data["lng"]))
            geom = LineString(coords, srid=21781)

            # remove redundant lat, lng columns in data
            data.drop(columns=["lat", "lng"], inplace=True)

            return geom, data
