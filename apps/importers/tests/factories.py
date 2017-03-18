from apps.importers import models
from apps.routes.tests.factories import RouteFactory


class SwitzerlandMobilityRouteFactory(RouteFactory):
    class Meta:
        model = models.SwitzerlandMobilityRoute

    source_id = 2191833


class StravaRouteFactory(RouteFactory):
    class Meta:
        model = models.StravaRoute

    source_id = 2325453
