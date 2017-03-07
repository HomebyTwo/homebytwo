from django.test import TestCase, override_settings
from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.exceptions import ValidationError
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.measure import Distance

import pandas as pd
import numpy as np

from apps.routes.models import Place
from apps.routes.models.track import DataFrameField

from . import factories

import os


class PlaceTestCase(TestCase):

    def setUp(self):
        # Add user to the test database
        self.user = factories.UserFactory()

    def test_string_method(self):
        name = 'place_name'
        place = factories.PlaceFactory(name=name)
        self.assertTrue(name in str(place))

    def test_save_homebytwo_place_sets_source_id(self):
        place = factories.PlaceFactory()
        self.assertEqual(place.data_source, 'homebytwo')
        self.assertEqual(place.source_id, str(place.id))

    def test_get_places_within(self):
        point = GEOSGeometry('POINT(1 1)')

        factories.PlaceFactory(geom='POINT(0 0)')
        factories.PlaceFactory(geom='POINT(4 4)')
        factories.PlaceFactory(geom='POINT(100 100)')
        factories.PlaceFactory(geom='POINT(10 10)')

        places = Place.objects.get_places_within(point, 6)
        self.assertEqual(places.count(), 2)

        places = Place.objects.get_places_within(point, 200)
        self.assertTrue(
            places[0].distance_from_line < places[1].distance_from_line)
        self.assertTrue(
            places[2].distance_from_line < places[3].distance_from_line)

        place = places[0]
        self.assertAlmostEqual(place.distance_from_line.m, 2**0.5)

    def test_get_places_from_line(self):
        line = GEOSGeometry(
            'LINESTRING(612190.0 612190.0, 615424.648017 129784.662852)',
            srid=21781
        )

        factories.PlaceFactory(
            geom=GEOSGeometry('POINT(615424 129744.0)', srid=21781)
        )

        factories.PlaceFactory(
            geom=GEOSGeometry('POINT(4.0 4.0)', srid=21781)
        )

        places = Place.objects.get_places_from_line(line, max_distance=50)

        self.assertEqual(len(list(places)), 1)
        self.assertTrue(places[0].line_location == 1.0)
        self.assertTrue(places[0].distance_from_line.m > 0)

    # Views
    def test_importer_view_not_logged_redirected(self):
        url = reverse('routes:importers')
        redirect_url = "/login/?next=" + url
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_importer_view_logged_in(self):
        content = 'Import routes'
        url = reverse('routes:importers')
        user = factories.UserFactory(password='testpassword')
        self.client.login(username=user.username, password='testpassword')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(content in str(response.content))


class DataFrameFieldTestCase(TestCase):
    def test_write_hdf5(self):
        data = pd.DataFrame(np.random.randn(10, 2))
        field = DataFrameField(max_length=100, save_to='test')
        filename = field.get_prep_value(data)
        fullpath = os.path.join(
            settings.BASE_DIR,
            settings.MEDIA_ROOT,
            field.save_to,
            filename,
        )

        self.assertEqual(len(filename), 35)  # = 32 + '.h5'
        self.assertTrue(os.path.exists(fullpath))

        os.remove(fullpath)

    def test_read_hdf5(self):
        random_data = pd.DataFrame(np.random.randn(10, 2))
        filename = 'testdata.h5'
        dirname = os.path.join(
            settings.BASE_DIR,
            settings.MEDIA_ROOT,
            'test',
        )

        if not os.path.exists(dirname):
            os.makedirs(dirname)

        fullpath = os.path.join(dirname, filename)
        random_data.to_hdf(fullpath, 'df')

        field = DataFrameField(max_length=100, save_to='test')
        data = field.to_python(filename)

        self.assertEqual(str(random_data), str(data))
        self.assertTrue(hasattr(data, 'filename'))

        os.remove(fullpath)

    def test_invalid_input(self):
        test_str = 'coucou!'
        field = DataFrameField(max_length=100, save_to='test')
        with self.assertRaises(ValidationError):
            field.get_prep_value(test_str)


@override_settings(
    GOOGLEMAPS_API_KEY='AIzabcdefghijklmnopqrstuvwxyz0123456789',
)
class RouteTestCase(TestCase):

    def setUp(self):
        self.user = factories.UserFactory()

    #########
    # Model #
    #########

    def test_get_length(self):
        route = factories.RouteFactory.build(length=12345)
        length = route.get_length()

        self.assertTrue(isinstance(length, Distance))
        self.assertEqual(length.km, 12.345)

    def test_get_totalup(self):
        route = factories.RouteFactory.build(totalup=1234)
        totalup = route.get_totalup()

        self.assertTrue(isinstance(totalup, Distance))
        self.assertAlmostEqual(totalup.ft, 4048.556430446194)

    def test_get_totaldown(self):
        route = factories.RouteFactory.build(totaldown=4321)
        totaldown = route.get_totaldown()

        self.assertTrue(isinstance(totaldown, Distance))
        self.assertAlmostEqual(totaldown.m, 4321)

    def test_get_start_altitude(self):
        data = pd.DataFrame(
            [[0, 0, 0, 0], [1000, 0, 1234, 1000]],
            columns=['lat', 'lng', 'altitude', 'length']
        )
        route = factories.RouteFactory.build(data=data)
        start_altitude = route.get_start_altitude()

        self.assertAlmostEqual(start_altitude.m, 0)

    def test_get_end_altitude(self):
        data = pd.DataFrame(
            [[0, 0, 0, 0], [600000, 0, 1234, 600000]],
            columns=['lat', 'lng', 'altitude', 'length']
        )
        route = factories.RouteFactory.build(data=data)

        end_altitude = route.get_end_altitude()

        self.assertAlmostEqual(end_altitude.m, 1234)

    def test_get_distance_data_from_line_location(self):
        data = pd.DataFrame(
            [[0, 0, 0, 0], [1000, 1000, 1000, 1414.2135624]],
            columns=['lat', 'lng', 'altitude', 'length']
        )
        route = factories.RouteFactory.build(data=data)

        # make the call
        point_altitude = route.get_distance_data_from_line_location(
            0.5,
            'altitude'
        )

        self.assertTrue(isinstance(point_altitude, Distance))
        self.assertAlmostEqual(point_altitude.m, 500)

    def test_get_start_and_end_places(self):
        route = factories.RouteFactory.build()
        factories.PlaceFactory(
            name="Start_Place",
            geom='POINT(%s %s)' % route.geom[0]
        )
        factories.PlaceFactory(
            name="End_Place",
            geom='POINT(%s %s)' % route.geom[-1]
        )
        start_place = route.get_closest_places_along_line()[0]
        end_place = route.get_closest_places_along_line(1)[0]

        self.assertEqual(start_place.distance_from_line.m, 0)
        self.assertEqual(start_place.name, 'Start_Place')

        self.assertEqual(end_place.distance_from_line.m, 0)
        self.assertEqual(end_place.name, 'End_Place')

    #########
    # Views #
    #########

    def test_route_detail_view_success(self):
        route = factories.RouteFactory()
        url = reverse('routes:detail', args=[route.id])
        route_name = route.name
        start_place_name = route.start_place.name
        end_place_name = route.end_place.name

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(route_name in str(response.content))
        self.assertTrue(start_place_name in str(response.content))
        self.assertTrue(end_place_name in str(response.content))
