from collections import namedtuple
from datetime import datetime

from django.contrib.gis.db import models
from django.core.serializers import serialize

from gpxpy.gpx import GPXWaypoint

from ...core.models import TimeStampedModel

PlaceTuple = namedtuple(
    "PlaceTuple",
    [
        "data_source",
        "source_id",
        "name",
        "country",
        "latitude",
        "longitude",
        "place_type",
        "altitude",
        "srid",
    ],
)


class Place(TimeStampedModel):
    """
    Places are geographic points.
    They have a name, description and geom
    Places are used to create checkpoints on routes and
    and for public transport connection.
    """

    BELAY = "BEL"
    BOAT_STATION = "BOA"
    BOULDER = "BLD"
    BUS_STATION = "BUS"
    CAVE = "CAV"
    CHAPEL = "CPL"
    CUSTOMHOUSE_24H = "C24"
    CUSTOMHOUSE_24H_LIMITED = "C24LT"
    CUSTOMHOUSE_LIMITED = "CLT"
    ENTRY_AND_EXIT = "EAE"
    EXIT = "EXT"
    FOUNTAIN = "FTN"
    FRIENDS_PLACE = "FRD"
    GYM = "GYM"
    HILL = "HIL"
    HOLIDAY_PLACE = "HOL"
    HOME = "HOM"
    INTERCHANGE = "ICG"
    LANDMARK = "LMK"
    LOADING_STATION = "LST"
    LOCAL_PLACE = "LPL"
    MONUMENT = "MNT"
    OPEN_BUILDING = "OBG"
    OTHER_PLACE = "CST"
    OTHER_STATION = "OTH"
    PARKING = "PKG"
    PASS = "PAS"
    PLACE = "PLA"
    POINT_OF_VIEW = "POV"
    ROAD_PASS = "RPS"
    SACRED_BUILDING = "SBG"
    SINGLE_BUILDING = "BDG"
    SOURCE = "SRC"
    SUMMIT = "SUM"
    TOWER = "TWR"
    TRAIN_STATION = "TRA"
    WATERFALL = "WTF"
    WAYSIDE_SHRINE = "SHR"
    WORK = "WRK"

    place_type = models.ForeignKey("PlaceType", on_delete="CASCADE")
    name = models.CharField(max_length=250)
    description = models.TextField(default="", blank=True)
    data_source = models.CharField(default="homebytwo", max_length=50)
    source_id = models.CharField("ID at the data source", max_length=50, null=True)
    country = models.ForeignKey(
        "Country",
        null=True,
        blank=True,
        related_name="places",
        on_delete="SET_NULL",
    )
    geom = models.PointField(srid=3857)
    altitude = models.FloatField(null=True, blank=True)

    class Meta:
        # The pair 'data_source' and 'source_id' should be unique together.
        constraints = [
            models.UniqueConstraint(
                name="unique place for source",
                fields=["data_source", "source_id"],
            ),
        ]

    def __str__(self):
        return "{0} - {1}".format(
            self.name,
            self.place_type.name,
        )

    def get_coords(self, srid=4326):
        """
        returns a tuple with the place coords transformed to the requested srid
        """
        return self.geom.transform(srid, clone=True).coords

    def get_geojson(self, fields):
        return serialize("geojson", [self], geometry_field="geom", fields=fields)

    def get_gpx_waypoint(self, route, line_location, start_time):
        """
        return the GPXWaypoint object of the place
        """

        lng, lat = self.get_coords()
        time = start_time + route.get_time_data(line_location, "schedule")
        altitude_on_route = route.get_distance_data(line_location, "altitude")

        return GPXWaypoint(
            name=self.name,
            longitude=lng,
            latitude=lat,
            elevation=altitude_on_route,
            type=self.place_type.name,
            time=time,
        )


class PlaceType(models.Model):
    """
    Like places, place types are downloaded from geonames at
    http://www.geonames.org/export/codes.html
    """

    FEATURE_CLASS_CHOICES = (
        ("A", "country, state, region,..."),
        ("H", "stream, lake,..."),
        ("L", "parks,area,..."),
        ("P", "city, village,..."),
        ("R", "road, railroad"),
        ("S", "spot, building, farm"),
        ("U", "undersea"),
        ("V", "forest,heath,..."),
    )

    feature_class = models.CharField(max_length=1, choices=FEATURE_CLASS_CHOICES)
    code = models.CharField(max_length=10, primary_key=True)
    name = models.CharField(max_length=256)
    description = models.CharField(max_length=512)


class Checkpoint(models.Model):
    """
    Intermediate model for route - place
    """

    route = models.ForeignKey("Route", on_delete=models.CASCADE)
    place = models.ForeignKey("Place", on_delete=models.CASCADE)

    # location on the route normalized 0=start 1=end
    line_location = models.FloatField(default=0)

    @property
    def altitude_on_route(self):
        return self.route.get_distance_data(self.line_location, "altitude")

    @property
    def distance_from_start(self):
        return self.route.get_distance_data(self.line_location, "distance")

    @property
    def cumulative_elevation_gain(self):
        return self.route.get_distance_data(
            self.line_location, "cumulative_elevation_gain"
        )

    @property
    def cumulative_elevation_loss(self):
        return self.route.get_distance_data(
            self.line_location, "cumulative_elevation_loss", absolute=True
        )

    @property
    def field_value(self):
        """
        value used in the ModelForm to serialize checkpoints
        """
        return "{}_{}".format(self.place.id, self.line_location)

    class Meta:
        ordering = ("line_location",)

        constraints = [
            models.UniqueConstraint(
                name="unique checkpoint on route",
                fields=["route", "place", "line_location"],
            ),
        ]

    def __str__(self):
        return "{0:.1f}km: {1} - {2}".format(
            self.distance_from_start.km,
            self.place.name,
            self.place.place_type.name,
        )

    def get_gpx_waypoint(self, route=None, start_time=datetime.utcnow()):
        """
        return the GPXWaypoint object for exporting routes to GPX
        """
        route = route or self.route

        return self.place.get_gpx_waypoint(
            route=route,
            line_location=self.line_location,
            start_time=start_time,
        )
