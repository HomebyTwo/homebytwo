from apps.importers import models
from apps.routes.tests.factories import RouteFactory


class SwitzerlandMobilityRouteFactory(RouteFactory):
    class Meta:
        model = models.SwitzerlandMobilityRoute

    source_id = 2191833
