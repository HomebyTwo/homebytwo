from django.contrib.gis.db import models
from django.core.serializers import serialize

from ...core.models import TimeStampedModel


class Place(TimeStampedModel):
    """
    Places are geographic points.
    They have a name, description and geom
    Places are used to create segments from routes and
    and for public transport connection.
    """

    PLACE = "PLA"
    LOCAL_PLACE = "LPL"
    SINGLE_BUILDING = "BDG"
    OPEN_BUILDING = "OBG"
    TOWER = "TWR"
    SACRED_BUILDING = "SBG"
    CHAPEL = "CPL"
    WAYSIDE_SHRINE = "SHR"
    MONUMENT = "MNT"
    FOUNTAIN = "FTN"
    SUMMIT = "SUM"
    HILL = "HIL"
    PASS = "PAS"
    BELAY = "BEL"
    WATERFALL = "WTF"
    CAVE = "CAV"
    SOURCE = "SRC"
    BOULDER = "BLD"
    POINT_OF_VIEW = "POV"
    BUS_STATION = "BUS"
    TRAIN_STATION = "TRA"
    OTHER_STATION = "OTH"
    BOAT_STATION = "BOA"
    EXIT = "EXT"
    ENTRY_AND_EXIT = "EAE"
    ROAD_PASS = "RPS"
    INTERCHANGE = "ICG"
    LOADING_STATION = "LST"
    PARKING = "PKG"
    CUSTOMHOUSE_24H = "C24"
    CUSTOMHOUSE_24H_LIMITED = "C24LT"
    CUSTOMHOUSE_LIMITED = "CLT"
    LANDMARK = "LMK"
    HOME = "HOM"
    WORK = "WRK"
    GYM = "GYM"
    HOLIDAY_PLACE = "HOL"
    FRIENDS_PLACE = "FRD"
    OTHER_PLACE = "CST"

    PLACE_TYPE_CHOICES = (
        (PLACE, "Place"),
        (LOCAL_PLACE, "Local Place"),
        (
            "Constructions",
            (
                (SINGLE_BUILDING, "Single Building"),
                (OPEN_BUILDING, "Open Building"),
                (TOWER, "Tower"),
                (SACRED_BUILDING, "Sacred Building"),
                (CHAPEL, "Chapel"),
                (WAYSIDE_SHRINE, "Wayside Shrine"),
                (MONUMENT, "Monument"),
                (FOUNTAIN, "Fountain"),
            ),
        ),
        (
            "Features",
            (
                (SUMMIT, "Summit"),
                (HILL, "Hill"),
                (PASS, "Pass"),
                (BELAY, "Belay"),
                (WATERFALL, "Waterfall"),
                (CAVE, "Cave"),
                (SOURCE, "Source"),
                (BOULDER, "Boulder"),
                (POINT_OF_VIEW, "Point of View"),
            ),
        ),
        (
            "Public Transport",
            (
                (BUS_STATION, "Bus Station"),
                (TRAIN_STATION, "Train Station"),
                (OTHER_STATION, "Other Station"),
                (BOAT_STATION, "Boat Station"),
            ),
        ),
        (
            "Roads",
            (
                (EXIT, "Exit"),
                (ENTRY_AND_EXIT, "Entry and Exit"),
                (ROAD_PASS, "Road Pass"),
                (INTERCHANGE, "Interchange"),
                (LOADING_STATION, "Loading Station"),
                (PARKING, "Parking"),
            ),
        ),
        (
            "Customs",
            (
                (CUSTOMHOUSE_24H, "Customhouse 24h"),
                (CUSTOMHOUSE_24H_LIMITED, "Customhouse 24h limited"),
                (CUSTOMHOUSE_LIMITED, "Customhouse limited"),
                (LANDMARK, "Landmark"),
            ),
        ),
        (
            "Personal",
            (
                (HOME, "Home"),
                (WORK, "Work"),
                (GYM, "Gym"),
                (HOLIDAY_PLACE, "Holiday Place"),
                (FRIENDS_PLACE, "Friend's place"),
                (OTHER_PLACE, "Other place"),
            ),
        ),
    )

    place_type = models.CharField(max_length=26, choices=PLACE_TYPE_CHOICES)
    name = models.CharField(max_length=250)
    description = models.TextField(default="", blank=True)
    altitude = models.FloatField(null=True)
    data_source = models.CharField(default="homebytwo", max_length=50)
    source_id = models.CharField("ID at the data source", max_length=50)
    public_transport = models.BooleanField(default=False)
    geom = models.PointField(srid=21781)

    class Meta:
        # The pair 'data_source' and 'source_id' should be unique together.
        unique_together = (
            "data_source",
            "source_id",
        )

    def __str__(self):
        return "{0} - {1}".format(self.name, self.get_place_type_display(),)

    def save(self, *args, **kwargs):
        """
        Source_id references the id at the data source.
        The pair 'data_source' and 'source_id' should be unique together.
        Places created in Homebytwo directly should thus have a source_id
        set.
        In other cases, e.g. importers.Swissname3dPlaces,
        the source_id will be set by the importer model.

        """
        super(Place, self).save(*args, **kwargs)

        # in case of manual homebytwo entries, the source_id will be empty.
        if self.source_id == "":
            self.source_id = str(self.id)
            self.save()

    def get_geojson(self, fields=["name", "place_type"]):
        return serialize("geojson", [self], geometry_field="geom", fields=fields)


class Checkpoint(models.Model):
    # Intermediate model for route - place
    route = models.ForeignKey("Route", on_delete=models.CASCADE)
    place = models.ForeignKey("Place", on_delete=models.CASCADE)

    # location on the route normalized 0=start 1=end
    line_location = models.FloatField(default=0)

    @property
    def altitude_on_route(self):
        return self.route.get_distance_data(self.line_location, "altitude")

    @property
    def distance_from_start(self):
        return self.route.get_distance_data(self.line_location, "length")

    @property
    def field_value(self):
        return "{}_{}".format(self.place.id, self.line_location)

    class Meta:
        ordering = ("line_location",)
        unique_together = ("route", "place", "line_location")

    def __str__(self):
        return "{0:.1f}km: {1} - {2}".format(
            self.distance_from_start.km,
            self.place.name,
            self.place.get_place_type_display(),
        )
