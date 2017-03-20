from django.test import TestCase, override_settings
from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.exceptions import ValidationError
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.measure import Distance

from apps.routes.models import Place
from apps.routes.models.track import DataFrameField, DataFrameFormField

from . import factories
from hb2.utils.factories import UserFactory

from pandas import DataFrame
import numpy as np


import os


class PlaceTestCase(TestCase):

    def setUp(self):
        # Add user to the test database
        self.user = UserFactory()

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
        user = UserFactory(password='testpassword')
        self.client.login(username=user.username, password='testpassword')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(content in str(response.content))


class DataFrameFieldTestCase(TestCase):

    def load_data(self, file='test.h5'):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        data_dir = 'data'
        json_file = file

        json_path = os.path.join(
            dir_path,
            data_dir,
            json_file,
        )

        return open(json_path).read()

    def test_model_field_get_prep_value(self):
        data = DataFrame(np.random.randn(10, 2))
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
        self.assertTrue((data == field.to_python(filename)).all().all())

        test_str = 'coucou!'
        field = DataFrameField(max_length=100, save_to='test')
        with self.assertRaises(ValidationError):
            field.get_prep_value(test_str)

    def test_model_field_to_python(self):
        field = DataFrameField(max_length=100, save_to='test')

        random_data = DataFrame(np.random.randn(10, 2))
        filename = field.get_prep_value(random_data)

        data = field.to_python(filename)
        self.assertTrue((random_data == data).all().all())
        self.assertTrue(hasattr(data, 'filename'))

        data = field.to_python(random_data)
        self.assertTrue((random_data == data).all().all())

        data = field.to_python(None)
        self.assertEqual(data, None)

        data = field.to_python('')
        self.assertEqual(data, None)

    def test_form_field_prepare_value(self):
        form_field = DataFrameFormField()
        value = DataFrame(
            [['a', 'b'], ['c', 'd']],
            columns=['col 1', 'col 2'])

        json = form_field.prepare_value(value)
        self.assertTrue((value == form_field.to_python(json)).all().all())
        self.assertTrue(isinstance(json, str))

        value = None
        json = form_field.prepare_value(None)
        self.assertEqual(value, form_field.to_python(json))
        self.assertTrue(isinstance(json, str))
        self.assertEqual(json, '')

        value = DataFrame()
        json = form_field.prepare_value(value)
        self.assertTrue((value == form_field.to_python(json)).all().all())

    def test_form_field_has_changed(self):
        form_field = DataFrameFormField()

        initial = DataFrame(
            [['a', 'b'], ['c', 'd']],
            columns=['col 1', 'col 2'])

        empty_data = None
        self.assertTrue(form_field.has_changed(initial, empty_data))
        self.assertFalse(form_field.has_changed(empty_data, empty_data))

        same_data = initial
        self.assertFalse(form_field.has_changed(initial, same_data))

        partly_changed_data = DataFrame(
            [['a', 'b'], ['c', 'f']],
            columns=['col 1', 'col 2'])
        self.assertTrue(form_field.has_changed(initial, partly_changed_data))

        different_shape_data = partly_changed_data = DataFrame(
            [['a', 'b', 'c'], ['c', 'f', 'g'], ['c', 'f', 'h']],
            columns=['col 1', 'col 2', 'col 3'])
        self.assertTrue(form_field.has_changed(initial, different_shape_data))

        changed_data = DataFrame(
            [['e', 'f'], ['g', 'h']],
            columns=['col 1', 'col 2'])
        self.assertTrue(form_field.has_changed(initial, changed_data))

    def test_form_field_to_python(self):
        form_field = DataFrameFormField()

        route = factories.RouteFactory()
        route_value = route.data.to_json(orient='records')
        self.assertFalse(form_field.to_python(route_value).empty)
        self.assertTrue(isinstance(
            form_field.to_python(route_value),
            DataFrame)
        )

        empty_df = DataFrame().to_json(orient='records')
        self.assertTrue(form_field.to_python(empty_df).empty)

        self.assertEqual(form_field.to_python(''), None)

    def test_data_to_form(self):
        pass


@override_settings(
    GOOGLEMAPS_API_KEY='AIzabcdefghijklmnopqrstuvwxyz0123456789',
)
class RouteTestCase(TestCase):

    def setUp(self):
        self.user = UserFactory()

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
        data = DataFrame(
            [[0, 0, 0, 0], [1000, 0, 1234, 1000]],
            columns=['lat', 'lng', 'altitude', 'length']
        )
        route = factories.RouteFactory.build(data=data)
        start_altitude = route.get_start_altitude()

        self.assertAlmostEqual(start_altitude.m, 0)

        route.data = None
        end_altitude = route.get_end_altitude()
        self.assertEqual(end_altitude, None)

    def test_get_end_altitude(self):
        data = DataFrame(
            [[0, 0, 0, 0], [600000, 0, 1234, 600000]],
            columns=['lat', 'lng', 'altitude', 'length']
        )
        route = factories.RouteFactory.build(data=data)

        end_altitude = route.get_end_altitude()

        self.assertAlmostEqual(end_altitude.m, 1234)

        route.data = None
        end_altitude = route.get_end_altitude()
        self.assertEqual(end_altitude, None)

    def test_get_distance_data_from_line_location(self):
        data = DataFrame(
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

    def test_route_route_view_success(self):
        route = factories.RouteFactory()
        url = reverse('routes:route', args=[route.id])
        route_name = route.name
        start_place_name = route.start_place.name
        end_place_name = route.end_place.name

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(route_name in str(response.content))
        self.assertTrue(start_place_name in str(response.content))
        self.assertTrue(end_place_name in str(response.content))
