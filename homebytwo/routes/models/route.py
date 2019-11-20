from collections import namedtuple

from django.conf import settings
from django.contrib.gis.db import models
from django.urls import reverse

from .track import Track

SourceLink = namedtuple('SourceLink', ['url', 'text'])


class RouteManager(models.Manager):
    def check_for_existing_routes(self, routes):
        """
        Split remote routes into old and new routes.
        Old routes have already been imported by the user.
        New routes have not been imported yet.
        """

        new_routes, old_routes = [], []

        for route in routes:
            # get_already_imported returns the route from db or None
            existing_route = route.get_already_imported()

            if existing_route:
                existing_route.url = existing_route.get_absolute_url()
                old_routes.append(existing_route)

            else:
                route.url = route.get_absolute_import_url()
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
        unique_together = ('athlete', 'data_source', 'source_id')

    def __str__(self):
        return 'Route: %s' % (self.name)

    def get_absolute_url(self):
        return reverse('routes:route', args=[self.pk])

    def get_absolute_import_url(self):
        """
        generate the import URL for a route stub
        based on data_source and source id.
        """
        route_import_view = "{}_route".format(self.data_source)
        return reverse(route_import_view, args=[self.source_id])

    @property
    def source_link(self):
        """
        retrieve the route URL on the site that the route was imported from

        The Strava API agreement requires that a link to
        the original resources be diplayed on the pages that use data from Strava.
        """

        if self.data_source == 'switzerland_mobility':
            url = settings.SWITZERLAND_MOBILITY_ROUTE_URL % self.source_id
            text = 'Switzerland Mobility'
            return SourceLink(url, text)

        if self.data_source == 'strava':
            url = settings.STRAVA_ROUTE_URL % int(self.source_id)
            text = 'Strava'
            return SourceLink(url, text)

        return

    def get_already_imported(self):
        """
        return route if it has already been imported to the database
        """
        route_class = type(self)

        try:
            return route_class.objects.get(
                data_source=self.data_source,
                source_id=self.source_id,
                athlete=self.athlete
            )

        except route_class.DoesNotExist:
            return None
