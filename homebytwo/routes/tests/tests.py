import os
from datetime import timedelta
from shutil import rmtree
from tempfile import mkdtemp
from unittest import skip
from uuid import uuid4

import numpy as np
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.measure import Distance
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.six import StringIO
from homebytwo.utils.factories import UserFactory
from pandas import DataFrame

from . import factories
from ..fields import DataFrameField, DataFrameFormField
from ..models import ActivityPerformance, Place
from ..templatetags.duration import baseround, nice_repr


def open_data(file):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    data_dir = 'data'

    path = os.path.join(
        dir_path,
        data_dir,
        file,
    )
    return open(path, 'rb')


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
            geom=GEOSGeometry('POINT(613807.32400 370987.3314)', srid=21781)
        )

        factories.PlaceFactory(
            geom=GEOSGeometry('POINT(4.0 4.0)', srid=21781)
        )

        places = Place.objects.get_places_from_line(line, max_distance=50)

        self.assertEqual(len(list(places)), 1)
        self.assertAlmostEqual(places[0].line_location, 0.5)
        self.assertTrue(places[0].distance_from_line.m > 0)


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


class RouteTestCase(TestCase):

    def setUp(self):
        self.user = UserFactory(password='testpassword')
        self.client.login(username=self.user.username, password='testpassword')

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
        route = factories.RouteFactory.build(data=data, length=600000)

        end_altitude = route.get_end_altitude()

        self.assertAlmostEqual(end_altitude.m, 1234)

        route.data = None
        end_altitude = route.get_end_altitude()
        self.assertEqual(end_altitude, None)

    def test_get_start_point(self):
        route = factories.RouteFactory.build()
        start_point = route.get_start_point()

        self.assertIsInstance(start_point, GEOSGeometry)

    def test_get_distance_data(self):
        data = DataFrame(
            [[0, 0, 0, 0], [707.106781187, 707.106781187, 1000, 1000]],
            columns=['lat', 'lng', 'altitude', 'length']
        )
        route = factories.RouteFactory.build(data=data, length=1000)

        # make the call
        point_altitude = route.get_distance_data(
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

    def test_find_additional_places(self):
        route = factories.RouteFactory(name='Haute-Cime')

        factories.PlaceFactory(
            name='Sur Frête',
            geom=GEOSGeometry(
                'POINT (565586.0225000009 112197.4462499991)',
                srid=21781
            )
        )
        factories.PlaceFactory(
            name='Noudane Dessus',
            geom=GEOSGeometry(
                'POINT (565091.2349999994 111464.0387500003)',
                srid=21781
            )
        )
        factories.PlaceFactory(
            name='Col du Jorat',
            geom=GEOSGeometry(
                'POINT (564989.3350000009 111080.0012499988)',
                srid=21781
            )
        )
        factories.PlaceFactory(
            name='Saut Peca',
            geom=GEOSGeometry(
                'POINT (564026.3412499987 110762.4175000004)',
                srid=21781
            )
        )
        factories.PlaceFactory(
            name='Haute Cime',
            geom=GEOSGeometry(
                'POINT (560188.0975000001 112309.0137500018)',
                srid=21781
            )
        )
        factories.PlaceFactory(
            name='Col des Paresseux',
            geom=GEOSGeometry(
                'POINT (560211.875 112011.8737500012)',
                srid=21781
            )
        )
        factories.PlaceFactory(
            name='Col de Susanfe',
            geom=GEOSGeometry(
                'POINT (559944.7375000007 110888.6424999982)',
                srid=21781
            )
        )
        factories.PlaceFactory(
            name='Cabane de Susanfe CAS',
            geom=GEOSGeometry(
                'POINT (558230.2575000003 109914.8912499994)',
                srid=21781
            )
        )
        factories.PlaceFactory(
            name="Pas d'Encel",
            geom=GEOSGeometry(
                'POINT (556894.5662500001 110045.9137500003)',
                srid=21781
            )
        )
        factories.PlaceFactory(
            name='Refuge de Bonaveau',
            geom=GEOSGeometry(
                'POINT (555775.7837500013 111198.6625000015)',
                srid=21781
            )
        )

        checkpoints = Place.objects.find_places_along_line(route.geom,
                                                           max_distance=100)
        self.assertEqual(len(checkpoints), 12)
        for checkpoint in checkpoints:
            self.assertNotEqual(checkpoint.line_location, 0)
            self.assertNotEqual(checkpoint.line_location, 1)

    def test_calculate_elevation_gain_distance(self):
        data = DataFrame({
            'altitude': [0, 1, 2, 3, 2, 1, 0],
            'length': [0, 1, 2, 2, 3, 4, 5],
        })

        route = factories.RouteFactory(data=data)

        route.calculate_elevation_gain_and_distance()

        self.assertListEqual(
            list(route.data),
            ['altitude', 'length', 'distance', 'gain']
        )

        self.assertListEqual(
            list(route.data.distance),
            [0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0]
        )

        self.assertListEqual(
            list(route.data.gain),
            [0.0, 1.0, 1.0, 1.0, -1.0, -1.0, -1.0]
        )

    def test_calculate_projected_time_schedule(self):
        activity_type = factories.ActivityTypeFactory()

        route = factories.RouteFactory(activity_type=activity_type)
        user = UserFactory()

        route.calculate_projected_time_schedule(user)
        total_default_time = route.get_data(1, 'schedule')

        ActivityPerformance.objects.create(
            athlete=user.athlete,
            activity_type=activity_type,
            slope_squared_param=activity_type.slope_squared_param / 2,
            slope_param=activity_type.slope_param / 2,
            flat_param=activity_type.flat_param / 2,
            total_elevation_gain_param=activity_type.total_elevation_gain_param,
        )

        route.calculate_projected_time_schedule(user)
        total_user_time = route.get_data(1, 'schedule')

        self.assertTrue(total_default_time > total_user_time)

    def test_schedule_display(self):
        duration = timedelta(seconds=30, minutes=1, hours=6)
        long_dspl = nice_repr(duration)
        self.assertEqual(long_dspl, '6 hours 1 minute 30 seconds')

        duration = timedelta(seconds=0)
        long_dspl = nice_repr(duration)
        self.assertEqual(long_dspl, '0 seconds')

        duration = timedelta(seconds=30, minutes=2, hours=2)
        hike_dspl = nice_repr(duration, display_format='hike')
        self.assertEqual(hike_dspl, '2 h 5 min')

        duration = timedelta(seconds=45, minutes=57, hours=2)
        hike_dspl = nice_repr(duration, display_format='hike')
        self.assertEqual(hike_dspl, '3 h')

        duration = timedelta(seconds=30, minutes=2, hours=6)
        hike_dspl = nice_repr(duration, display_format='hike')
        self.assertEqual(hike_dspl, '6 h')

    def test_base_round(self):
        values = [0, 3, 4.85, 12, -7]
        rounded = [baseround(value) for value in values]

        self.assertEqual(rounded, [0, 5, 5, 10, -5])

    @override_settings(
        STRAVA_ROUTE_URL='https://strava_route_url/%d',
        SWITZERLAND_MOBILITY_ROUTE_URL='https://switzerland_mobility_route_url/%d',
    )
    def test_source_link(self):
        route = factories.RouteFactory(
            data_source='strava',
            source_id=777)
        source_url = 'https://strava_route_url/777'
        self.assertEqual(route.source_link.url, source_url)
        self.assertEqual(route.source_link.text, 'Strava')

        route = factories.RouteFactory(
            data_source='switzerland_mobility',
            source_id=777)
        source_url = 'https://switzerland_mobility_route_url/777'
        self.assertEqual(route.source_link.url, source_url)
        self.assertEqual(route.source_link.text, 'Switzerland Mobility')

        route = factories.RouteFactory()
        self.assertIsNone(route.source_link)

    #########
    # Views #
    #########

    def test_route_404(self):
        url = 'routes/0/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_route_edit_404(self):
        url = 'routes/0/edit/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_route_image_404(self):
        url = 'routes/0/image/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_route_delete_404(self):
        url = 'routes/0/delete/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_route_view_success_owner(self):
        route = factories.RouteFactory(owner=self.user)
        url = reverse('routes:route', args=[route.id])
        route_name = route.name
        start_place_name = route.start_place.name
        end_place_name = route.end_place.name
        edit_url = reverse('routes:edit', args=[route.id])
        edit_button = ('<a href="%s">Edit Route</a>'
                       % edit_url)

        response = self.client.get(url)
        response_content = response.content.decode('UTF-8')

        self.assertEqual(response.status_code, 200)
        self.assertIn(route_name, response_content)
        self.assertIn(start_place_name, response_content)
        self.assertIn(end_place_name, response_content)
        self.assertIn(edit_button, response_content)

    def test_route_view_success_not_owner(self):
        route = factories.RouteFactory(owner=factories.UserFactory())
        url = reverse('routes:route', args=[route.id])
        edit_url = reverse('routes:edit', args=[route.id])

        response = self.client.get(url)
        response_content = response.content.decode('UTF-8')

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(edit_url, response_content)

    def test_route_view_success_not_logged_in(self):
        route = factories.RouteFactory(owner=factories.UserFactory())
        url = reverse('routes:route', args=[route.id])
        edit_url = reverse('routes:edit', args=[route.id])
        route_name = route.name

        self.client.logout()
        response = self.client.get(url)
        response_content = response.content.decode('UTF-8')

        self.assertEqual(response.status_code, 200)
        self.assertIn(route_name, response_content)
        self.assertNotIn(edit_url, response_content)

    def test_route_view_success_no_start_place(self):
        route = factories.RouteFactory(
            owner=factories.UserFactory(),
            start_place=None
        )
        url = reverse('routes:route', args=[route.id])
        route_name = route.name
        end_place_name = route.end_place.name

        response = self.client.get(url)
        response_content = response.content.decode('UTF-8')

        self.assertEqual(response.status_code, 200)
        self.assertIn(route_name, response_content)
        self.assertIn(end_place_name, response_content)

    def test_route_view_success_no_end_place(self):
        route = factories.RouteFactory(
            owner=factories.UserFactory(),
            end_place=None
        )
        url = reverse('routes:route', args=[route.id])
        route_name = route.name
        start_place_name = route.start_place.name

        response = self.client.get(url)
        response_content = response.content.decode('UTF-8')

        self.assertEqual(response.status_code, 200)
        self.assertIn(route_name, response_content)
        self.assertIn(start_place_name, response_content)

    def test_get_route_delete_view(self):
        route = factories.RouteFactory()
        url = reverse('routes:delete', args=[route.id])
        response = self.client.get(url)
        response_content = response.content.decode('UTF-8')
        content = '<h1>Delete %s</h1>' % route.name

        self.assertEqual(response.status_code, 200)
        self.assertIn(content, response_content)

    def test_get_route_delete_not_logged(self):
        route = factories.RouteFactory()
        url = reverse('routes:delete', args=[route.id])
        self.client.logout()

        response = self.client.get(url)
        redirect_url = "/login/?next=" + url

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_post_route_delete_view(self):
        route = factories.RouteFactory()
        url = reverse('routes:delete', args=[route.id])
        post_data = {}
        response = self.client.post(url, post_data)

        redirect_url = reverse('routes:routes')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    @skip  # until rules is implemented
    def test_post_route_delete_not_owner(self):
        route = factories.RouteFactory(owner=factories.UserFactory())
        url = reverse('routes:delete', args=[route.id])
        post_data = {}
        response = self.client.post(url, post_data)

        self.assertEqual(response.status_code, 401)

    def test_get_route_image_form(self):
        route = factories.RouteFactory(owner=self.user)
        url = reverse('routes:image', args=[route.id])
        response = self.client.get(url)
        response_content = response.content.decode('UTF-8')

        content = '<h3>Edit image for %s</h3>' % route.name

        self.assertEqual(response.status_code, 200)
        self.assertIn(content, response_content)

    def test_get_route_image_form_not_logged(self):
        route = factories.RouteFactory(owner=self.user)
        url = reverse('routes:image', args=[route.id])
        self.client.logout()

        response = self.client.get(url)
        redirect_url = "/login/?next=" + url

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_post_route_image(self):
        route = factories.RouteFactory(owner=self.user)
        url = reverse('routes:image', args=[route.id])
        with open_data('image.jpg') as image:
            post_data = {
                'image': SimpleUploadedFile(image.name, image.read())
            }

        response = self.client.post(url, post_data)
        redirect_url = reverse('routes:route', args=[route.id])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    @skip  # until rules is implemented
    def test_post_route_image_not_owner(self):
        route = factories.RouteFactory(owner=factories.UserFactory())
        url = reverse('routes:image', args=[route.id])

        with open_data('image.jpg') as image:
            post_data = {
                'image': SimpleUploadedFile(image.name, image.read())
            }

        response = self.client.post(url, post_data)

        self.assertEqual(response.status_code, 401)

    def test_get_route_edit_form(self):
        route = factories.RouteFactory(owner=self.user)
        url = reverse('routes:edit', args=[route.id])
        response = self.client.get(url)
        response_content = response.content.decode('UTF-8')

        content = '<h2 class="text-center">Edit Route: %s</h2>' % route.name

        self.assertEqual(response.status_code, 200)
        self.assertIn(content, response_content)

    def test_get_route_edit_form_not_logged(self):
        route = factories.RouteFactory(owner=self.user)
        url = reverse('routes:edit', args=[route.id])
        self.client.logout()

        response = self.client.get(url)
        redirect_url = "/login/?next=" + url

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_post_route_edit_form(self):
        route = factories.RouteFactory(owner=self.user)
        url = reverse('routes:edit', args=[route.id])
        with open_data('image.jpg') as image:
            post_data = {
                'name': route.name,
                'activity_type': route.activity_type.id,
                'description': route.description,
                'image': SimpleUploadedFile(image.name, image.read())
            }

        response = self.client.post(url, post_data)
        redirect_url = reverse('routes:route', args=[route.id])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    @skip  # until rules is implemented
    def test_post_route_edit_not_owner(self):
        route = factories.RouteFactory(owner=factories.UserFactory())
        url = reverse('routes:edit', args=[route.id])

        with open_data('image.jpg') as image:
            post_data = {
                'name': route.name,
                'description': route.description,
                'image': SimpleUploadedFile(image.name, image.read())
            }

        response = self.client.post(url, post_data)

        self.assertEqual(response.status_code, 401)

    #######################
    # Management Commands #
    #######################

    @override_settings(MEDIA_ROOT=mkdtemp())
    def test_cleanup_route_data_no_data(self):
        # No files in data directory
        out = StringIO()
        call_command('cleanup_route_data', stdout=out)
        self.assertIn('No files to delete.', out.getvalue())
        rmtree(settings.MEDIA_ROOT, ignore_errors=True)

    @override_settings(MEDIA_ROOT=mkdtemp())
    def test_cleanup_route_data_routes(self):
        # five routes no extra files
        out = StringIO()
        [factories.RouteFactory() for i in range(5)]

        call_command('cleanup_route_data', stdout=out)
        self.assertIn('No files to delete.', out.getvalue())
        rmtree(settings.MEDIA_ROOT, ignore_errors=True)

    @override_settings(MEDIA_ROOT=mkdtemp())
    def test_cleanup_route_data_delete_trash(self):
        # five random files not in DB
        data_dir = os.path.join(
            settings.BASE_DIR,
            settings.MEDIA_ROOT,
            'data'
        )

        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        out = StringIO()
        for i in range(5):
            filename = uuid4().hex + '.h5'
            fullpath = os.path.join(data_dir, filename)
            with open(fullpath, 'wb') as file_:
                file_.write(os.urandom(64))

        call_command('cleanup_route_data', stdout=out)
        self.assertIn('Successfully deleted 5 files.', out.getvalue())
        rmtree(settings.MEDIA_ROOT, ignore_errors=True)

    @override_settings(MEDIA_ROOT=mkdtemp())
    def test_cleanup_route_data_missing_route_file(self):
        # One deleted route data file one random file
        data_dir = os.path.join(
            settings.BASE_DIR,
            settings.MEDIA_ROOT,
            'data'
        )
        out = StringIO()
        [factories.RouteFactory() for i in range(5)]
        file_to_delete = os.listdir(data_dir)[0]
        os.remove(os.path.join(data_dir, file_to_delete))
        filename = uuid4().hex + '.h5'
        fullpath = os.path.join(data_dir, filename)
        with open(fullpath, 'wb') as file_:
            file_.write(os.urandom(64))

        call_command('cleanup_route_data', stdout=out)
        self.assertIn('Successfully deleted 1 files.', out.getvalue())
        rmtree(settings.MEDIA_ROOT, ignore_errors=True)
