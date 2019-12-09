from django.contrib.gis.geos import LineString

from pandas import DataFrame
from polyline import decode
from social_django.models import UserSocialAuth
from stravalib import unithelper

from ...routes.models import ActivityType, Route, RouteManager
from ...routes.utils import Link
from ..exceptions import StravaMissingCredentials


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

        # retrieve routes list from Strava
        strava_routes = athlete.strava_client.get_routes(athlete_id=athlete.strava_id)

        # create model instances with Strava routes data
        return [
            StravaRoute(
                source_id=strava_route.id,
                name=strava_route.name,
                totalup=unithelper.meters(strava_route.elevation_gain).num,
                length=unithelper.meters(strava_route.distance).num,
                athlete=athlete,
            )
            for strava_route in strava_routes
        ]

    def check_user_credentials(self, request):
        """
        view function provided to check whether a user
        has access to Strava.
        """
        # check if the user has an associated Strava account
        try:
            request.user.social_auth.get(provider="strava")

        # redirect to login with strava page
        except UserSocialAuth.DoesNotExist:
            raise StravaMissingCredentials


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
    def get_route_details(self):
        """
        retrieve route details including streams from strava.
        the source_id of the model instance must be set.
        """
        strava_client = self.athlete.strava_client

        # Retrieve route detail and streams
        strava_route = strava_client.get_route(self.source_id)
        raw_streams = strava_client.get_route_streams(self.source_id)

        self.name = strava_route.name
        self.description = strava_route.description
        self.totalup = unithelper.meters(strava_route.elevation_gain).num
        self.length = unithelper.meters(strava_route.distance).num
        self.geom = self._polyline_to_linestring(strava_route.map.polyline)
        self.data = self._data_from_streams(raw_streams)

        # Strava only knows two activity types for routes: '1' for ride, '2' for run
        if strava_route.type == "1":
            self.activity_type = ActivityType.objects.filter(name="Bike").get()
        if strava_route.type == "2":
            self.activity_type = ActivityType.objects.filter(name="Run").get()

        # transform geom coords to CH1903 / LV03
        self._transform_coords(self.geom)

        # compute elevation
        self.calculate_cummulative_elevation_differences()

        # calculate schedule for route owner
        self.calculate_projected_time_schedule(self.athlete.user)

        # retrieve totaldown from computed data
        self.totaldown = abs(
            self.get_data(1, "totaldown",)  # line location of the last datapoint
        )

    def _polyline_to_linestring(self, polyline):
        """
        by default, Strava returns a geometry encoded as a polyline.
        convert the polyline into a linestring for import into postgis
        with the correct srid.
        """

        # decode the polyline.
        coords = decode(polyline)

        # Inverse tupple because Google Maps works in lat, lng
        coords = [(lng, lat) for lat, lng in coords]

        # Create line string and specify SRID
        linestring = LineString(coords)
        linestring.srid = 4326

        # return the linestring with the correct SRID
        return linestring

    def _data_from_streams(self, streams):
        """
        convert route raw streams into a pandas DataFrame.
        the stravalib client creates a list of dicts:
        `[stream_type: <Stream object>, stream_type: <Stream object>, ...]`
        """

        data = DataFrame()

        for key, stream in streams.items():
            # split latlng in two columns
            if key == "latlng":
                data["lat"], data["lng"] = zip(
                    *[(coords[0], coords[1]) for coords in stream.data]
                )

            # rename distance to length
            elif key == "distance":
                data["length"] = stream.data

            else:
                data[key] = stream.data

        return data

    def _transform_coords(self, geom, target_srid=21781):
        """
        transform coordinates from one system to the other.
        defaults: from WGS 84 to CH1903 / LV03
        """

        # transform geometry to target srid
        geom.transform(target_srid)
