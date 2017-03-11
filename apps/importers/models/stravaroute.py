from __future__ import unicode_literals

from django.contrib.gis.db import models
from django.contrib.gis.geos import LineString

from apps.routes.models import Route

from stravalib.client import Client
from stravalib import unithelper

from polyline import decode


class StravaRouteManager(models.Manager):

    # login to Switzerland Mobility and retrieve route list
    def get_routes_list_from_server(self, user):
        # Initialize Stravalib client
        client = Client()

        # Get Strava access token
        client.access_token = user.athlete.strava_token
        routes = client.get_routes()

        for route in routes:

            coords = decode(route.map.summary_polyline)

            # Inverse tupple because Google Maps works in lat, lng
            coords = [(lng, lat) for lat, lng in coords]

            # Create line string and specify SRID
            line = LineString(coords)
            line.srid = 4326

            strava_route, created = StravaRoute.objects.get_or_create(
                strava_route_id=route.id,
                defaults={
                        'name': route.name,
                        'totalup': unithelper.meters(route.elevation_gain),
                        'totaldown': 0,
                        'length': unithelper.meters(route.distance),
                        'geom': line,
                        'description': route.description,
                        'type': route.type,
                        'sub_type': route.sub_type,
                        'strava_timestamp': route.timestamp,
                        'user': user,
                    }

                )


class StravaRoute(Route):
    # Extends Route class with Strava attributes and methods
    strava_route_id = models.BigIntegerField(unique=True)

    # Type 1 for ride, 2 for run
    type = models.CharField(max_length=1)

    # Sub-type 1 for ride, 2 for run
    sub_type = models.CharField(max_length=1)

    # Time of last updated as unix timestamp
    strava_timestamp = models.IntegerField()

    objects = StravaRouteManager()

    # retrieve map.wanderland.ch information for a route
    def get_route_details_from_server(self, user):
        # Initialize Stravalib client
        client = Client()

        # Get Strava access token
        client.access_token = user.athlete.strava_token

        # Retrieve route detail
        route = client.get_route(self.strava_route_id)

        # Decode polyline
        coords = decode(route.map.polyline)

        # Inverse tupple because Google Maps works in lat, lng
        coords = [(lng, lat) for lat, lng in coords]

        # Create line string and specify SRID
        line = LineString(coords)
        line.srid = 4326

        if len(self.geom) != len(line):
            self.geom = line

        if route.timestamp != self.strava_timestamp:
            self.name = route.name
            self.totalup = unithelper.meters(route.elevation_gain)
            self.totaldown = 0
            self.length = unithelper.meters(route.distance)
            self.geom = line
            self.description = route.description
            self.type = route.type
            self.sub_type = route.sub_type
            self.strava_timestamp = route.timestamp

        self.save()
