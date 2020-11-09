from factory import Sequence

from ...importers import models
from ...routes.tests.factories import RouteFactory


class SwitzerlandMobilityRouteFactory(RouteFactory):
    class Meta:
        model = models.SwitzerlandMobilityRoute

    source_id = Sequence(lambda n: 10000 + n)


class StravaRouteFactory(RouteFactory):
    class Meta:
        model = models.StravaRoute

    source_id = Sequence(lambda n: 10000 + n)
