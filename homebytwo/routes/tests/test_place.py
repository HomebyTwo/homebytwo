from django.contrib.gis.geos import GEOSGeometry
from django.test import TestCase

from ...utils.factories import UserFactory
from ..utils import get_places_from_line, get_places_within
from .factories import PlaceFactory


class PlaceTestCase(TestCase):
    def setUp(self):
        # Add user to the test database
        self.user = UserFactory()

    def test_string_method(self):
        name = "place_name"
        place = PlaceFactory(name=name)
        self.assertTrue(name in str(place))

    def test_get_places_within(self):
        point = GEOSGeometry("POINT(1 1)")

        PlaceFactory(geom="POINT(0 0)")
        PlaceFactory(geom="POINT(4 4)")
        PlaceFactory(geom="POINT(100 100)")
        PlaceFactory(geom="POINT(10 10)")

        places = get_places_within(point, 6)
        self.assertEqual(places.count(), 2)

        places = get_places_within(point, 200)
        self.assertTrue(places[0].distance_from_line < places[1].distance_from_line)
        self.assertTrue(places[2].distance_from_line < places[3].distance_from_line)

        place = places[0]
        self.assertAlmostEqual(place.distance_from_line.m, 2 ** 0.5)

    def test_get_places_from_line(self):
        line = GEOSGeometry(
            "LINESTRING(612190.0 612190.0, 615424.648017 129784.662852)", srid=21781
        )

        PlaceFactory(geom=GEOSGeometry("POINT(613807.32400 370987.3314)", srid=21781))

        PlaceFactory(geom=GEOSGeometry("POINT(4.0 4.0)", srid=21781))

        places = get_places_from_line(line, max_distance=50)

        self.assertEqual(len(list(places)), 1)
        self.assertAlmostEqual(places[0].line_location, 0.5)
        self.assertTrue(places[0].distance_from_line.m > 0)
