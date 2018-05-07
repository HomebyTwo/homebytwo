from django.contrib.gis.db import models
from django.urls import reverse

from .track import Track


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
                old_routes.append(route)
            else:
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

    def get_absolute_url(self):
        return reverse('routes:route', kwargs={'pk': self.pk})

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

    def __str__(self):
        return 'Route: %s' % (self.name)
