from collections import deque, namedtuple

from django.conf import settings
from django.contrib.gis.db import models
from django.urls import reverse

from ..fields import LineSubstring
from ..utils import create_segments_from_checkpoints, get_places_from_line
from .place import RoutePlace
from .track import Track

SourceLink = namedtuple('SourceLink', ['url', 'text'])


class RouteManager(models.Manager):
    def check_for_existing_routes(self, owner, routes, data_source):
        """
        Split remote routes into old and new routes.
        Old routes have already been imported by the user.
        New routes have not been imported yet.
        """
        new_routes = []
        old_routes = []

        for route in routes:
            source_id = route.source_id
            saved_route = self.filter(owner=owner)
            saved_route = saved_route.filter(data_source=data_source)
            saved_route = saved_route.filter(source_id=source_id)

            if saved_route.exists():
                route = saved_route.get()
                route.url = reverse('routes:route', args=[route.id])
                old_routes.append(route)

            else:
                # named view where the route can be imported e.g.
                # `strava_route` or `switzerland_mobility_route`
                route_import_view = "{}_route".format(data_source)
                route.url = reverse(route_import_view, args=[route.source_id])
                new_routes.append(route)

        return new_routes, old_routes


class Route(Track):

    # source and unique id (at the source) that the route came from
    source_id = models.BigIntegerField()
    data_source = models.CharField(
        'Where the route came from',
        default='homebytwo',
        max_length=50
    )

    # A route can have checkpoints
    places = models.ManyToManyField(
        'Place',
        through='RoutePlace',
        blank=True,
    )

    # Each route is made of segments
    # segments = models.ManyToManyField(Segment)

    class Meta:
        unique_together = ('owner', 'data_source', 'source_id')

    def __str__(self):
        return 'Route: %s' % (self.name)

    def get_absolute_url(self):
        return reverse('routes:route', kwargs={'pk': self.pk})

    @property
    def source_link(self):

        if self.data_source == 'switzerland_mobility':
            url = settings.SWITZERLAND_MOBILITY_ROUTE_URL % self.source_id
            text = 'Switzerland Mobility'
            return SourceLink(url, text)

        if self.data_source == 'strava':
            url = settings.STRAVA_ROUTE_URL % int(self.source_id)
            text = 'Strava'
            return SourceLink(url, text)

        return

    def already_imported(self):
        """
        check if route has already been imported to the database
        """
        route_class = type(self)
        imported_route = route_class.objects.filter(
            source_id=self.source_id,
            owner=self.owner
        )

        return imported_route.exists()

    def find_checkpoints(self, max_distance=75):
        """
        The recursive strategy creates a new line substrings between
        the found places and runs the query on these line substrings again.

        If a new place is found on the line substring. We look for other places
        again on the newly created segements. if no new place is found,
        the segment is discarded from the recursion.

        For example, if the geometry passes through these places:

            Start---A---B---A---End

        1/  the first time around, we find these places:

            Start---A---B-------End

        2/  we check for further places along each subsegment:
            a) Start---A
            b) A---B
            c) B---End

        3/  find no additional places in a) and b) but find the place A in c)

            B---A---End

        4/  we check for further places in each subsegment
            and find no additional place.

        """
        # add places from initial request that found each visited place once
        checkpoints = list(self.routeplace_set.all())
        segments = deque(create_segments_from_checkpoints(checkpoints))

        while segments:
            segment = segments.popleft()
            # find additional places along the segment
            new_places = self.find_places_in_segment(segment, self.geom, max_distance)

            if new_places:
                start, end = segment
                checkpoints += [
                    RoutePlace(route=self, place=place, line_location=place.line_location) for place in new_places
                ]
                segments.extend(
                    create_segments_from_checkpoints(new_places, start, end)
                )

        checkpoints = sorted(checkpoints, key=lambda o: o.line_location)

        return checkpoints

    def find_places_in_segment(self, segment, line, max_distance):
        start, end = segment

        # create the Linestring geometry
        subline = LineSubstring(line, start, end)

        # find places within max_distance of the linestring
        places = get_places_from_line(subline, max_distance)

        # iterate over found places to change the line_location
        # from the location on the segment to the location on
        # the original linestring.
        for place in places:
            # relative line location to the start point of the subline
            length = (place.line_location * (end - start))

            # update attribute with line location on the original line
            place.line_location = start + length

        return places
