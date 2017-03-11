import factory
import factory.fuzzy
import factory.django

from apps.routes import models
from hb2.utils.factories import UserFactory
from django.contrib.gis.geos import GEOSGeometry

import pandas as pd


class PlaceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Place

    place_type = factory.Iterator(
        models.Place.PLACE_TYPE_CHOICES,
        getter=lambda c: c[0]
    )
    name = factory.fuzzy.FuzzyText()
    description = factory.fuzzy.FuzzyText(length=100)
    altitude = factory.fuzzy.FuzzyInteger(5000)
    public_transport = factory.Iterator([True, False])
    geom = GEOSGeometry('POINT(0 0)', srid=21781)


class RouteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Route
        exclude = ('route_geojson', 'route_profile')

    route_geojson = (
        '{"type": "LineString", '
        '"coordinates": [[612190.0, 129403.0], '
        '[615424.648017, 129784.662852]]}'
    )

    route_profile = [
        [568013.411408, 113191.647718, 448.54, 0],
        [568013.255765, 113191.426207, 448.54, 0.270724790281],
        [568007.927619, 113220.802611, 448.5, 30.1264144543],
        [567991.117585, 113298.81999, 448.66, 109.93423817],
        [567997.554327, 113303.788421, 448.84, 118.065471914],
        [567992.670315, 113329.49396, 448.84, 144.230875445]
    ]

    name = factory.fuzzy.FuzzyText()
    source_id = factory.Sequence(lambda n: '%d' % n)
    data_source = 'homebytwo'
    description = factory.fuzzy.FuzzyText(length=100)
    user = factory.SubFactory(UserFactory)
    totalup = factory.fuzzy.FuzzyInteger(5000)
    totaldown = factory.fuzzy.FuzzyInteger(5000)
    length = factory.fuzzy.FuzzyInteger(50000)
    geom = GEOSGeometry(route_geojson, srid=21781)
    start_place = factory.SubFactory(
        PlaceFactory,
        geom='POINT (%s %s)' % geom.coords[0]
    )
    end_place = factory.SubFactory(
        PlaceFactory,
        geom='POINT (%s %s)' % geom.coords[-1]
    )
    data = pd.DataFrame(
        route_profile,
        columns=['lat', 'lng', 'altitude', 'length']
    )
