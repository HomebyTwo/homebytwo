from collections import deque
from datetime import datetime, timedelta
from tempfile import NamedTemporaryFile
from uuid import uuid4

from django.apps import apps
from django.conf import settings
from django.contrib.gis.db import models
from django.urls import reverse

import gpxpy
import gpxpy.gpx
from garmin_uploader.api import GarminAPI, GarminAPIException
from garmin_uploader.workflow import Activity as GarminActivity
from requests.exceptions import HTTPError

from ..models import Checkpoint, Track
from ..utils import (
    GARMIN_ACTIVITY_TYPE_MAP,
    Link,
    create_segments_from_checkpoints,
    get_places_from_segment,
)


class RouteQuerySet(models.QuerySet):
    def for_user(self, user):
        """
        return all routes of a given user.
        this is convenient with the 'request.user' object in views.
        """
        return self.filter(athlete=user.athlete)


class RouteManager(models.Manager):
    def get_queryset(self):
        return RouteQuerySet(self.model, using=self._db)

    def for_user(self, user):
        return self.get_queryset().for_user(user)


def authenticate_on_garmin(garmin_api):
    # sign-in to Homebytwo account
    try:
        return garmin_api.authenticate(
            settings.GARMIN_CONNECT_USERNAME, settings.GARMIN_CONNECT_PASSWORD
        )
    except Exception as e:
        raise GarminAPIException("Unable to sign-in: {}".format(e))


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

    # uuid field to generate unique file names
    uuid = models.UUIDField(default=uuid4, editable=False)

    # source and unique id (at the source).
    # Can be null for some sources such as GPX import
    source_id = models.BigIntegerField(null=True, blank=True)
    data_source = models.CharField(
        "Where the route came from", default="homebytwo", max_length=50
    )

    # many-2-many relationship to Place over the Checkpoint relationship table
    places = models.ManyToManyField("Place", through="Checkpoint", blank=True)

    # Activity id on Garmin
    garmin_id = models.BigIntegerField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="unique route for athlete",
                fields=["athlete", "data_source", "source_id"],
            ),
        ]

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
            "gpx": ("routes:gpx", route_kwargs),
            "garmin_upload": ("routes:garmin_upload", route_kwargs),
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
    def gpx_url(self):
        return self.get_absolute_url("gpx")

    @property
    def garmin_upload_url(self):
        return self.get_absolute_url("garmin_upload")

    @property
    def import_url(self):
        return self.get_absolute_url("import")

    @property
    def source_link(self):
        """
        retrieve the route URL on the site that the route was imported from

        The Strava API agreement requires that a link to the original resources
        be displayed on the pages that use data from Strava.
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
        if self.garmin_id and self.garmin_id > 1:
            return settings.GARMIN_ACTIVITY_URL.format(self.garmin_id)

    @property
    def svg(self):
        """
        return the default svg image to display for each data source.
        """
        data_source_svg = {
            "switzerland_mobility": "images/switzerland_mobility.svg",
            "strava": "images/strava.svg",
            "homebytwo": "images/homebytwo.svg",
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
        proxy_model = self.DATA_SOURCE_PROXY_MODELS.get(self.data_source)
        return apps.get_model(proxy_model) if proxy_model else None

    @property
    def gpx_filename(self):
        return "homebytwo_{}.gpx".format(self.pk)

    @classmethod
    def get_or_stub(cls, source_id, athlete):
        """
        return stub or existing object of the correct proxy class.
        also return a boolean of whether exists.
        """

        try:
            return (
                cls.objects.get(
                    source_id=source_id,
                    athlete=athlete,
                ),
                True,
            )

        except cls.DoesNotExist:
            return (
                cls(
                    source_id=source_id,
                    athlete=athlete,
                ),
                False,
            )

    def get_route_details(self, cookies=None):
        """
        retrieve route details from the remote service.

        Must be implemented in in the proxy class of the remote service,
        e.g. SwitzerlandMobilityRoute, StravaRoute. The `cookies` parameter
        expects authorization cookies for Switzerland Mobility stored in the session
        and is only used for Switzerland Mobility.
        """
        raise NotImplementedError

    def get_route_data(self, cookies=None):
        """
        retrieve route details from the remote service.

        Must be implemented in in the proxy class of the remote service,
        e.g. SwitzerlandMobilityRoute, StravaRoute. The `cookies` parameter
        expects authorization cookies for Switzerland Mobility stored in the session
        and is only used for Switzerland Mobility.
        """

        # get the proxy class corresponding to the data_source
        route_class = self.proxy_class

        if route_class:
            proxy_route = route_class.objects.get(pk=self.pk)
            return proxy_route.get_route_data(cookies)

        else:
            raise NotImplementedError

    def update_from_remote(self, cookies=None):
        """
        update an existing route with the data from the remote service.
        """
        route_class = self.proxy_class

        if route_class:
            route = route_class.objects.get(pk=self.pk)

            # overwrite route with remote info
            route.get_route_details(cookies)

            return route

    def find_possible_checkpoints(self, max_distance=75, updated_geom=False):
        """
        return places as checkpoints based on the route geometry.

        start from existing checkpoints by default. you can use updated_geom=True
        to discard existing checkpoints if the geometry of the route has changed.

        A single place can be returned multiple times: the recursive strategy creates
        a new line substrings between the found checkpoints and runs the query on these
        line substrings again. If a new place is found on the line substring.
        We look for other checkpoints again on the newly created segments.
        If no new checkpoint is found, the segment is discarded from the recursion.

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
        # Start with the checkpoints that have been saved before or not
        checkpoints = list(self.checkpoint_set.all()) if not updated_geom else list()
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

    def get_gpx(self, start_time=None):
        """
        returns the route as a GPX with track schedule and waypoints
        https://www.topografix.com/gpx.asp
        """
        # GPX requires datetime objects but route.data["schedule"] is in timedelta
        start_time = start_time or datetime.utcnow()

        # instantiate GPX object
        gpx = gpxpy.gpx.GPX()
        gpx.creator = "Homebytwo -- homebytwo.ch"

        # add route waypoints
        gpx.waypoints.extend(self.get_gpx_waypoints(start_time))
        gpx.tracks.append(self.get_gpx_track(start_time))

        return gpx.to_xml()

    def get_gpx_waypoints(self, start_time):
        """
        return the set of all waypoints including start and end place
        as GPXWaypoint objects.
        """

        # get GPX from checkpoints
        gpx_checkpoints = [
            checkpoint.get_gpx_waypoint(route=self, start_time=start_time)
            for checkpoint in self.checkpoint_set.all()
        ]
        gpx_waypoints = deque(gpx_checkpoints)

        # retrieve start_place GPX
        if self.start_place:
            gpx_start_place = self.start_place.get_gpx_waypoint(
                route=self, line_location=0, start_time=start_time
            )
            gpx_waypoints.appendleft(gpx_start_place)

        # retrieve end_place GPX
        if self.end_place:
            gpx_end_place = self.end_place.get_gpx_waypoint(
                route=self, line_location=1, start_time=start_time
            )
            gpx_waypoints.append(gpx_end_place)
        return gpx_waypoints

    def get_gpx_track(self, start_time):
        """
        return the GPXTrack object corresponding to the route

        According to GPX specifications, GPS tracks can contain one or more segments
        of continuous GPS tracking. For our schedule, we create a single segment.
        """

        # Instantiate GPX Track
        gpx_track = gpxpy.gpx.GPXTrack(name=self.name)

        # GPX Segment in Track
        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)

        # create a clone of the route geom in SRID 4326
        geom = self.geom.transform(4326, clone=True)

        # we cannot start from the route geometry
        # because it can have a different number of coords than the number of rows
        # in the route data. We start from the distance column in the route data and
        # save the corresponding Point in the Linestring geometry to lat, lng columns.
        self.data["lng"], self.data["lat"] = zip(  # unpack list of coords tuples
            *(self.data["distance"] / self.data["distance"].max())  # line location
            .apply(lambda x: geom.interpolate_normalized(x).coords)  # get Point
            .to_list()  # dump list of coords tuples
        )

        # create the GPXTrackPoints from the route data and append them to the segment
        for lng, lat, altitude, schedule in zip(
            self.data.lng,
            self.data.lat,
            self.data.altitude,
            self.data.schedule,
        ):
            gpx_track_point = gpxpy.gpx.GPXTrackPoint(
                latitude=lat,
                longitude=lng,
                elevation=altitude,
                time=start_time + timedelta(seconds=schedule),
            )

            gpx_segment.points.append(gpx_track_point)

        return gpx_track

    def upload_to_garmin(self, athlete=None):
        """
        uploads a route schedule as activity to the Homebytwo account on
        Garmin Connect using the garmin_uploader library:
        https://github.com/JohanWieslander/garmin-uploader

        Athletes can then use the "race against activity" feature on
        compatible Garmin devices.
        """

        # calculate schedule
        athlete = athlete or self.athlete
        self.calculate_projected_time_schedule(athlete.user)

        # instantiate API from garmin_uploader and authenticate
        garmin_api = GarminAPI()
        session = authenticate_on_garmin(garmin_api)

        # delete existing activity on Garmin
        if self.garmin_id > 1:
            self.delete_garmin_activity(session)

        # write GPX content to temporary file
        with NamedTemporaryFile(mode="w+b", suffix=".gpx") as file:
            file.write(bytes(self.get_gpx(), encoding="utf-8"))

            # instantiate activity object from garmin_upload
            activity = GarminActivity(
                path=file.name,
                name="HB2 {}".format(self.name),
                type=GARMIN_ACTIVITY_TYPE_MAP.get(self.activity_type.name, "other"),
            )

            # upload to Garmin
            activity.id, uploaded = garmin_api.upload_activity(session, activity)

        if uploaded:
            self.garmin_id = activity.id
            self.save(update_fields=["garmin_id"])

            # adapt type and name on Garmin connect
            garmin_api.set_activity_name(session, activity)
            garmin_api.set_activity_type(session, activity)

        return self.garmin_activity_url, uploaded

    def delete_garmin_activity(self, session):
        """
        delete an existing activity on Garmin based on the route garmin_id

        If it fails
        """
        delete_url = (
            "https://connect.garmin.com/modern/proxy/activity-service/activity/{}"
        )
        garmin_response = session.delete(delete_url.format(self.garmin_id))

        try:
            # 404 is ok, job was already done
            if not garmin_response.status_code == 404:
                garmin_response.raise_for_status()

        except HTTPError as error:
            raise GarminAPIException(
                "Failed to delete activity {}: {}".format(self.garmin_id, error)
            )
        else:
            self.garmin_id = None
            self.save(update_fields=["garmin_id"])
