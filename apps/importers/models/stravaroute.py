from __future__ import unicode_literals

from django.contrib.gis.geos import LineString

from apps.routes.models import Route, RouteManager, ActivityType

from pandas import DataFrame
from polyline import decode
from stravalib import unithelper


class StravaRouteManager(RouteManager):

    def get_queryset(self):
        """
        Returns query_sets with Strava Routes only.
        This method is required because StravaRoute
        is a proxy class.
        """
        return super(StravaRouteManager, self). \
            get_queryset().filter(data_source='strava')

    # login to Switzerland Mobility and retrieve route list
    def get_routes_list_from_server(self, user, strava_client):

        # retrieve routes from strava
        strava_routes = strava_client.get_routes()

        # create model instances with Strava routes data
        routes = []

        for strava_route in strava_routes:
            route = StravaRoute(
                source_id=strava_route.id,
                data_source='strava',
                name=strava_route.name,
                totalup=unithelper.meters(strava_route.elevation_gain).num,
                length=unithelper.meters(strava_route.distance).num,
            )

            routes.append(route)

        # split into new and existing routes
        return self.check_for_existing_routes(
            user=user,
            routes=routes,
            data_source='strava'
        )


class StravaRoute(Route):

    """
    Proxy for Route Model with specific methods and custom manager.
    """

    class Meta:
        proxy = True

    # custom manager
    objects = StravaRouteManager()

    # retrieve strava information for a route
    def get_route_details(self, client):
        """
        retrieve route details including streams from strava.
        the source_id of the model instance must be set.
        """

        # Retrieve route detail and streams
        strava_route = client.get_route(self.source_id)
        raw_streams = client.get_route_streams(self.source_id)

        self.name = strava_route.name
        self.description = strava_route.description
        self.totalup = unithelper.meters(strava_route.elevation_gain).num
        self.length = unithelper.meters(strava_route.distance).num
        self.geom = self._polyline_to_linestring(strava_route.map.polyline)
        self.data = self._data_from_streams(raw_streams)

        # Strava activity types: '1' for ride, '2' for run
        if strava_route.type == '1':
            self.activity_type = ActivityType.objects.filter(name='Bike').get()
        if strava_route.type == '2':
            self.activity_type = ActivityType.objects.filter(name='Run').get()

        # transform geom coords to CH1903 / LV03
        self._transform_coords(self.geom)

        # compute elevation
        self.calculate_cummulative_elevation_differences()

        # retrieve totaldown from computed data
        self.totaldown = abs(self.get_data(
            1,  # line location of the last datapoint
            'totaldown',
        ))

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
            if key == 'latlng':
                data['lat'], data['lng'] = zip(
                    *[(coords[0], coords[1]) for coords in stream.data]
                )

            # rename distance to length
            elif key == 'distance':
                data['length'] = stream.data

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

    def save(self, *args, **kwargs):
        """
        Set the data_source of the route to strava
        when saving the route.
        """
        # set the data_source of the route to switzerland_mobility
        self.data_source = 'strava'

        # Save with the parent method
        super(StravaRoute, self).save(*args, **kwargs)
