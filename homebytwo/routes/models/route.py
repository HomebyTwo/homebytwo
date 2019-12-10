from collections import deque
from datetime import datetime, timedelta
from tempfile import NamedTemporaryFile

from django.apps import apps
from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.urls import reverse

import gpxpy
import gpxpy.gpx
from garmin_uploader.api import GarminAPI, GarminAPIException
from garmin_uploader.workflow import Activity as GarminActivity
from requests.exceptions import HTTPError

from ..models import ActivityType, Checkpoint, Track
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
    Subclass of track with source information and relations to checkpoints.

    The StravaRoute and SwitzerlandMobilityRoute proxy models
    inherit from Route.
    """

    # link the data source to the corresponding proxy models
    DATA_SOURCE_PROXY_MODELS = {
        "strava": "importers.StravaRoute",
        "switzerland_mobility": "importers.SwitzerlandMobilityRoute",
    }

    # source and unique id (at the source) that the route came from
    source_id = models.BigIntegerField()
    data_source = models.CharField(
        "Where the route came from", default="homebytwo", max_length=50
    )

    # many-2-many relationship to Place over the Checkpoint relationship table
    places = models.ManyToManyField("Place", through="Checkpoint", blank=True)

    # Activity id on Garmin
    garmin_id = models.BigIntegerField(blank=True, null=True)

    class Meta:
        unique_together = ("athlete", "data_source", "source_id")

    objects = RouteManager()

    def __str__(self):
        return "{activity_type}: {name}".format(
            activity_type=str(self.activity_type), name=self.name
        )

    def get_absolute_url(self, action="display"):
        """
        return the relative URL for the route based on the action requested.

        """
        route_kwargs = {"pk": self.pk}
        import_kwargs = {"data_source": self.data_source, "source_id": self.source_id}

        action_reverse = {
            "display": ("routes:route", route_kwargs),
            "edit": ("routes:edit", route_kwargs),
            "update": ("routes:update", route_kwargs),
            "delete": ("routes:delete", route_kwargs),
            "import": ("import_route", import_kwargs),
        }
        if action_reverse.get(action):
            return reverse(action_reverse[action][0], kwargs=action_reverse[action][1])

    @property
    def display_url(self):
        return self.get_absolute_url("display")

    @property
    def edit_url(self):
        return self.get_absolute_url("edit")

    @property
    def update_url(self):
        return self.get_absolute_url("update")

    @property
    def delete_url(self):
        return self.get_absolute_url("delete")

    @property
    def import_url(self):
        return self.get_absolute_url("import")

    @property
    def source_link(self):
        """
        retrieve the route URL on the site that the route was imported from

        The Strava API agreement requires that a link to the original resources
        be diplayed on the pages that use data from Strava.
        """

        # Switzerland Mobility Route
        if self.data_source == "switzerland_mobility":
            return Link(
                url=settings.SWITZERLAND_MOBILITY_ROUTE_URL % int(self.source_id),
                text="Switzerland Mobility Plus",
            )

        # Strava Route
        elif self.data_source == "strava":
            return Link(
                url=settings.STRAVA_ROUTE_URL % int(self.source_id), text="Strava"
            )

    @property
    def garmin_activity_url(self):
        return (
            settings.GARMIN_ACTIVITY_URL.format(self.garmin_id)
            if self.garmin_id > 0
            else None
        )

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
    def proxy_class(self):
        return apps.get_model(self.DATA_SOURCE_PROXY_MODELS[self.data_source])

    @property
    def can_be_imported(self):
        """
        check if a route stub is already in the database.
        """
        if not self.pk:
            return not Route.objects.filter(
                data_source=self.data_source,
                source_id=self.source_id,
                athlete=self.athlete,
            ).exists()

    @property
    def gpx_filename(self):
        return "homebytwo_{}.gpx".format(self.pk)

    def update_from_remote(self):
        """
        update an existing route with the data from the remote service.
        """
        route_class = self.proxy_class

        if route_class:
            route = route_class.objects.get(pk=self.pk)

            # overwrite route with remote info
            route.get_route_details()

            # reset the checkpoints, the price of updating from remote
            route.checkpoint_set.all().delete()

            return route

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

    def get_gpx(self):
        """
        returns the route as a GPX with track schedule and waypoints
        https://www.topografix.com/gpx.asp
        """
        # instantiate GPX object
        gpx = gpxpy.gpx.GPX()
        gpx.creator = "Homebytwo -- homebytwo.ch"

        # GPX requires datetime objects, route.data["schedule"] id in timedelta
        start_datetime = datetime.utcnow()

        # append route checkpoints as GPX waypoints
        for checkpoint in self.checkpoint_set.all():
            longitude, latitude = checkpoint.place.geom.transform(
                4326, clone=True
            ).coords
            datetime_at_checkpoint = start_datetime + self.get_time_data(
                checkpoint.line_location, "schedule"
            )
            waypoint = gpxpy.gpx.GPXWaypoint(
                name=checkpoint.place.name,
                longitude=longitude,
                latitude=latitude,
                elevation=checkpoint.altitude_on_route,
                type=checkpoint.place.get_place_type_display(),
                time=datetime_at_checkpoint,
            )
            gpx.waypoints.append(waypoint)

        # GPX Track
        gpx_track = gpxpy.gpx.GPXTrack(name=self.name)
        gpx_track.type = self.activity_type.name
        gpx.tracks.append(gpx_track)

        # GPX Segment in Track
        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)

        data = self.data
        for lng, lat, altitude, seconds in zip(
            data["lng"], data["lat"], data["altitude"], data["schedule"]
        ):
            lng, lat = Point(lat, lng, srid=21781).transform(4326, clone=True).coords
            schedule = start_datetime + timedelta(seconds=seconds)
            gpx_segment.points.append(
                gpxpy.gpx.GPXTrackPoint(
                    latitude=lat, longitude=lng, elevation=altitude, time=schedule
                )
            )
        return gpx.to_xml()

    def upload_to_garmin(self, athlete=None):
        """
        uploads a route schedule as activity to the Homebytwo account on
        Garmin Connect using the garmin_uploader library:
        https://github.com/JohanWieslander/garmin-uploader

        Athletes can then use the "race against activity" feature on
        compatible Garmin devices.
        """

        activity_type_map = {
            ActivityType.ALPINESKI: "resort_skiing_snowboarding",
            ActivityType.BACKCOUNTRYSKI: "backcountry_skiing_snowboarding",
            ActivityType.ELLIPTICAL: "elliptical",
            ActivityType.HANDCYCLE: "cycling",
            ActivityType.HIKE: "hiking",
            ActivityType.ICESKATE: "skating",
            ActivityType.INLINESKATE: "skating",
            ActivityType.NORDICSKI: "cross_country_skiing",
            ActivityType.RIDE: "cycling",
            ActivityType.ROCKCLIMBING: "rock_climbing",
            ActivityType.ROWING: "rowing",
            ActivityType.RUN: "running",
            ActivityType.SNOWBOARD: "resort_skiing_snowboarding",
            ActivityType.SNOWSHOE: "hiking",
            ActivityType.STAIRSTEPPER: "fitness_equipment",
            ActivityType.STANDUPPADDLING: "stand_up_paddleboarding",
            ActivityType.SWIM: "swimming",
            ActivityType.VIRTUALRIDE: "cycling",
            ActivityType.VIRTUALRUN: "running",
            ActivityType.WALK: "walk",
            ActivityType.WEIGHTTRAINING: "fitness_equipment",
            ActivityType.WORKOUT: "strength_training",
        }

        # retrieve athlete
        athlete = athlete or self.athlete

        # calculate schedule if needed
        if not athlete == self.athlete or "schedule" not in self.data.columns:
            self.calculate_projected_time_schedule(athlete.user)

            # adding schedule to old routes one-by-one, instead of migrating
            if athlete == self.athlete.user:
                self.save()

        # instantiate API from garmin_uploader and authenticate
        garmin_api = GarminAPI()
        session = garmin_api.authenticate(
            settings.GARMIN_CONNECT_USERNAME, settings.GARMIN_CONNECT_PASSWORD
        )

        # delete existing activity on Garmmin
        if self.garmin_id:
            delete_url = "https://connect.garmin.com/modern/proxy/activity-service/activity/{}"
            garmin_response = session.delete(delete_url.format(self.garmin_id))
            try:
                garmin_response.raise_for_status()
            except HTTPError as error:
                raise GarminAPIException(
                    "Failed to delete activity {}: {}".format(self.garmin_id, error)
                )
            else:
                self.garmin_id = None
                self.save()

        # write GPX content to temporary file
        with NamedTemporaryFile(mode="w+b", suffix=".gpx") as file:
            file.write(bytes(self.get_gpx(), encoding="utf-8"))

            # instantiate activity object from garmin_uploade
            activity = GarminActivity(
                path=file.name,
                name="Homebytwo {}".format(str(self)),
                type=activity_type_map.get(self.activity_type.name, "other"),
            )

            # upload to Garmin
            activity.id, uploaded = garmin_api.upload_activity(session, activity)

        if uploaded:
            self.garmin_id = activity.id
            self.save()

            # adapt type and name on Garmin connect
            garmin_api.set_activity_name(session, activity)
            garmin_api.set_activity_type(session, activity)

        return self.garmin_activity_url, uploaded
