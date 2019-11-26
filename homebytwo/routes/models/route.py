from collections import deque

from django.conf import settings
from django.contrib.gis.db import models
from django.urls import reverse

from ..models import Checkpoint, Track
from ..utils import Link, create_segments_from_checkpoints, get_places_from_segment


class RouteQuerySet(models.QuerySet):
    def for_user(self, user):
        """
        return all routes of a given user.
        this is convinient with the 'request.user' object in views.
        """
        return self.filter(athlete=user.athlete)


class RouteManager(models.Manager):
    def get_queryset(self):
        return RouteQuerySet(self.model, using=self._db)

    def for_user(self, user):
        return self.get_queryset().for_user(user)


class Route(Track):
    """

    specific instance of track that holds source info and checkpoints

    The StravaRoute and SwitzerlandMobilityRoute proxy models
    inherit from Route.
    """

    # source and unique id (at the source) that the route came from
    source_id = models.BigIntegerField()
    data_source = models.CharField(
        "Where the route came from", default="homebytwo", max_length=50
    )

    places = models.ManyToManyField("Place", through="Checkpoint", blank=True)

    class Meta:
        unique_together = ("athlete", "data_source", "source_id")

    objects = RouteManager()

    def __str__(self):
        return "Route: %s" % (self.name)

    def get_absolute_url(self):
        return reverse("routes:route", args=[self.pk])

    def get_absolute_import_url(self):
        """
        generate the import URL for a route stub
        based on data_source and source id.
        """
        return reverse(
            "import_route",
            kwargs={"data_source": self.data_source, "source_id": self.source_id},
        )

    @property
    def source_link(self):
        """
        retrieve the route URL on the site that the route was imported from

        The Strava API agreement requires that a link to the original resources
        be diplayed on the pages that use data from Strava.
        """
        switzerland_mobility_url = settings.SWITZERLAND_MOBILITY_ROUTE_URL % self.source_id
        switzerland_mobility_text = "Switzerland Mobility Plus"

        strava_url = settings.STRAVA_ROUTE_URL % int(self.source_id)
        strava_text = "Strava"

        data_source_link = {
            "switzerland_mobility": Link(switzerland_mobility_url, switzerland_mobility_text),
            "strava": Link(strava_url, strava_text),

        }

        return data_source_link.get(self.data_source)

    @property
    def url(self):
        """
        Return the the absolute url if the route exists in the database,
        return the import url if it does not exist in the database.
        """
        if self.pk:
            return self.get_absolute_url()
        else:
            return self.get_absolute_import_url()

    @property
    def svg(self):
        """
        return the default svg image to display for each data source.
        """
        data_source_svg = {
            "switzerland_mobility": "images/switzerland_mobility.svg",
            "strava": "images/strava.svg",
        }

        return data_source_svg.get(self.data_source)

    @property
    def svg_muted(self):
        """
        return the default svg image to display for each data source.
        """
        data_source_svg = {
            "switzerland_mobility": "images/switzerland_mobility_muted.svg",
            "strava": "images/strava_muted.svg",
        }

        return data_source_svg.get(self.data_source)

    @property
    def source_name(self):
        words = self.data_source.split("_")
        return " ".join([word.capitalize() for word in words])

    def refresh_from_db_if_exists(self):
        """
        tries to refresh a stub route with DB data if it already exists.
        returns True if found in DB.
        """
        try:
            self = Route.objects.get(
                data_source=self.data_source,
                source_id=self.source_id,
                athlete=self.athlete,
            )
            return self, True

        except Route.DoesNotExist:
            return self, False

    def find_possible_checkpoints(self, max_distance=75):
        """
        The recursive strategy creates a new line substrings between
        the found checkpoints and runs the query on these line substrings again.
        If a new place is found on the line substring. We look for other checkpoints
        again on the newly created segements. If no new checkpoint is found,
        the segment is discarded from the recursion.

        For example, if the route passes through these checkpoints:
            Start---A---B---A---End
        1/  the first time around, we find these checkpoints:
            Start---A---B-------End
        2/  we check for further checkpoints along each subsegment:
            a) Start---A
            b) A---B
            c) B---End
        3/  find no additional checkpoints in a) and b) but find the checkpoint A in c)
            B---A---End
        4/  we check for further checkpoints in each subsegment
            and find no additional place.
        """
        # Start with the checkpoints that have been saved before
        checkpoints = list(self.checkpoint_set.all())
        segments = deque(create_segments_from_checkpoints(checkpoints))

        while segments:
            segment = segments.popleft()

            # find additional checkpoints along the segment
            new_places = get_places_from_segment(segment, self.geom, max_distance)

            if new_places:
                # create checkpoint stubs and add them to the list
                checkpoints += [
                    Checkpoint(
                        route=self, place=place, line_location=place.line_location
                    )
                    for place in new_places
                    if Checkpoint not in checkpoints
                ]

                # create new segments between the newly found places
                start, end = segment
                segments.extend(
                    create_segments_from_checkpoints(new_places, start, end)
                )

        checkpoints = sorted(checkpoints, key=lambda o: o.line_location)

        return checkpoints
