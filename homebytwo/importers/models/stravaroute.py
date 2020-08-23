from django.contrib.gis.geos import LineString

from pandas import DataFrame
from stravalib import unithelper

from ...routes.models import ActivityType, Route, RouteManager
from ...routes.utils import Link
from ..utils import check_strava_credentials


class StravaRouteManager(RouteManager):
    def get_queryset(self):
        """
        Returns querysets with Strava Routes only.
        This method is required because StravaRoute
        is a proxy class.
        Methods from the RouteManager, e.g. for_user can also be used.
        """
        return super().get_queryset().filter(data_source="strava")

    # login to Strava and retrieve route list
    def get_remote_routes_list(self, athlete, session):
        """
        fetches the athlete's routes list from Strava and returns them
        as a list of StravaRoute stubs.
        """

        # ensure athlete has a Strava account
        check_strava_credentials(athlete.user)

        # retrieve routes list from Strava
        strava_routes = athlete.strava_client.get_routes(athlete_id=athlete.strava_id)

        # create model instances with Strava routes data
        return [
            StravaRoute(
                source_id=strava_route.id,
                name=strava_route.name,
                total_elevation_gain=unithelper.meters(strava_route.elevation_gain).num,
                total_distance=unithelper.meters(strava_route.distance).num,
                athlete=athlete,
            )
            for strava_route in strava_routes
        ]


class StravaRoute(Route):

    """
    Proxy for Route Model with specific methods and custom manager.
    """

    # data source name to display in templates
    DATA_SOURCE_NAME = "Strava"
    DATA_SOURCE_LINK = Link("https://www.strava.com/athlete/routes", DATA_SOURCE_NAME,)

    def __init__(self, *args, **kwargs):
        """
        Set the data_source of the route to strava
        when instatiatind a route.
        """
        super().__init__(*args, **kwargs)
        self.data_source = "strava"

    class Meta:
        proxy = True

    # custom manager
    objects = StravaRouteManager()

    # retrieve strava information for a route
    def get_route_details(self, cookies=None):
        """
        retrieve route details including streams from strava.
        the source_id of the model instance must be set.
        """

        # ensure athlete is connected to Strava
        check_strava_credentials(self.athlete.user)
        strava_client = self.athlete.strava_client

        # Retrieve route details from Strava API
        strava_route = strava_client.get_route(self.source_id)

        # set route name and description
        self.name = strava_route.name
        self.description = strava_route.description if strava_route.description else ""

        # use Strava route distance and elevation_gain until we calculate them from data
        self.total_elevation_gain = unithelper.meters(strava_route.elevation_gain).num
        self.total_distance = unithelper.meters(strava_route.distance).num

        # Strava only knows two activity types for routes: '1' for ride, '2' for run
        if strava_route.type == "1":
            self.activity_type = ActivityType.objects.get(name=ActivityType.RIDE)
        if strava_route.type == "2":
            self.activity_type = ActivityType.objects.get(name=ActivityType.RUN)

        # create route data and geo from Strava API streams
        self.get_route_data_streams(strava_client)

    def get_route_data_streams(self, strava_client):
        """
        convert route raw streams into a pandas DataFrame and create the geom
        the stravalib client creates a list of dicts:
        `[stream_type: <Stream object>, stream_type: <Stream object>, ...]`
        """
        # retrieve route streams from Strava API
        route_streams = strava_client.get_route_streams(self.source_id)

        data = DataFrame()

        for key, stream in route_streams.items():
            # create route geom from latlng stream
            if key == "latlng":
                coords = [(lng, lat) for lat, lng in stream.data]
                self.geom = LineString(coords, srid=4326).transform(21781, clone=True)

            # import other streams
            else:
                data[key] = stream.data

        self.data = data
