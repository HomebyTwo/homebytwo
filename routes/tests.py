from django.test import TestCase, override_settings
from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.measure import Distance

import pandas as pd
import numpy as np

from .models import Place, Route
from .models.track import DataFrameField

import os
import httpretty


class PlaceTestCase(TestCase):

    def setUp(self):
        self.data = {
            'place_type': 'Church',
            'name': 'Place_Name',
            'description': 'Place_description',
            'altitude': 1000,
            'public_transport': True,
            'geom': 'POINT(0 0)',
        }

        # Add user to the test database
        self.user = User.objects.create_user(
            'testuser',
            'test@test.com',
            'test'
        )

    def test_string_method(self):
        name = 'place_name'
        place = Place(name=name)
        self.assertTrue(name in str(place))

    def test_save_homebytwo_place_sets_source_id(self):
        place = Place(**self.data)
        place.save()
        self.assertEqual(place.data_source, 'homebytwo')
        self.assertEqual(place.source_id, str(place.id))

    def test_get_places_within(self):
        point = GEOSGeometry('POINT(1 1)')

        place1 = Place(**self.data)
        place1.save()

        place2 = Place(**self.data)
        place2.geom = 'POINT(4 4)'
        place2.save()

        place3 = Place(**self.data)
        place3.geom = 'POINT(100 100)'
        place3.save()

        place4 = Place(**self.data)
        place4.geom = 'POINT(10 10)'
        place4.save()

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

        place1 = Place(**self.data)
        place1.geom = GEOSGeometry('POINT(615424 129744.0)', srid=21781)
        place1.save()

        place2 = Place(**self.data)
        place2.geom = GEOSGeometry('POINT(4.0 4.0)', srid=21781)
        place2.save()

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
        self.client.login(username='testuser', password='test')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(content in str(response.content))


@override_settings(
    MEDIA_ROOT='/vagrant/media',
)
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
        fullpath = os.path.join(settings.MEDIA_ROOT, 'test', filename)
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
        route_profile = [
            [568013.411408, 113191.647718, 448.54, 0],
            [568013.255765, 113191.426207, 448.54, 0.270724790281],
            [568007.927619, 113220.802611, 448.5, 30.1264144543],
            [567991.117585, 113298.81999, 448.66, 109.93423817],
            [567997.554327, 113303.788421, 448.84, 118.065471914],
            [567992.670315, 113329.49396, 448.84, 144.230875445],
            [567982.142681, 113324.991885, 448.66, 155.680755432],
            [567825.108411, 113263.572455, 448.95, 324.298987629],
            [567805.006096, 113259.566356, 449.54, 344.79659528],
            [567756.065116, 113264.385232, 453.52, 393.974243719],
            [567753.982811, 113264.952183, 454.16, 396.132351085],
            [567697.087589, 113269.925166, 467.42, 453.244493654],
            [567654.720749, 113247.584864, 489.67, 501.140612288],
            [567634.952208, 113248.246574, 498.52, 520.920225531],
            [567622.41276, 113257.540659, 509.16, 536.528485133],
            [567594.644631, 113221.115459, 526.1, 582.330933093],
            [567581.65074, 113232.079578, 536.52, 599.332495338],
            [567561.742847, 113221.180862, 540.88, 622.028447225],
            [567561.085718, 113242.639704, 550.11, 643.497348344],
            [567554.022114, 113250.459356, 557.67, 654.034969345],
            [567527.847037, 113237.482232, 565.25, 683.250382751],
            [567508.595677, 113248.146643, 578.16, 705.258211983],
            [567496.774919, 113247.432056, 586.32, 717.100548893],
            [567465.134759, 113209.249599, 606.3, 766.688851865],
            [567465.610755, 113168.559752, 616.7, 807.381482224],
            [567434.435383, 113173.730251, 628.39, 838.982714121],
            [567414.473182, 113167.16784, 637.7, 859.995918235],
            [567448.051134, 113134.859436, 650.49, 906.593255683],
            [567447.402683, 113114.85279, 656.18, 926.610407955],
            [567426.861904, 113101.289904, 668.13, 951.224945855],
            [567392.265872, 113116.706468, 678.69, 989.100477199],
            [567344.864798, 113135.082782, 683.39, 1039.93895385],
            [567346.535866, 113201.329552, 689.27, 1106.20679664],
        ]

        route_geojson = (
            '{"type": "LineString", '
            '"coordinates": [[612190.0, 129403.0], '
            '[615424.648017, 129784.662852]]}'
        )

        # Add user to the test database
        self.user = User.objects.create_user(
            'testuser',
            'test@test.com',
            'test'
        )

        start_place = Place(
            place_type='Train Station',
            name='Start_Place',
            description='Place_description',
            altitude=500,
            public_transport=True,
            geom='POINT(612190.0 129403.0)',
        )
        start_place.save()

        end_place = Place(
            place_type='Train Station',
            name='End_Place',
            description='Place_description',
            altitude=1500,
            public_transport=True,
            geom='POINT(615424.648017 129784.662852)',
        )
        end_place.save()

        self.google_elevation_json = (
            '{"status": "OK",'
            ' "results":'
            '    [{"location": {"lat": 46.31592, "lng": 7.5969},'
            '      "elevation": 123.456,'
            '      "resolution": 19.08790397644043}]'
            '}')

        self.route = Route(
            name='Test Name',
            source_id=1,
            data_source='homebytwo',
            description='Test description',
            user=self.user,
            totalup=1234,
            totaldown=4321,
            length=12345,
            geom=GEOSGeometry(route_geojson, srid=21781),
            start_place=start_place,
            end_place=end_place,
            data=pd.DataFrame(
                route_profile,
                columns=['lat', 'lng', 'altitude', 'length']
            )
        )

    #########
    # Model #
    #########

    def test_get_length(self):
        route = self.route
        length = route.get_length()

        self.assertTrue(isinstance(length, Distance))
        self.assertEqual(length.km, 12.345)

    def test_get_totalup(self):
        route = self.route
        totalup = route.get_totalup()

        self.assertTrue(isinstance(totalup, Distance))
        self.assertAlmostEqual(totalup.ft, 4048.556430446194)

    def test_get_totaldown(self):
        route = self.route
        totaldown = route.get_totaldown()

        self.assertTrue(isinstance(totaldown, Distance))
        self.assertAlmostEqual(totaldown.m, 4321)

    def test_get_start_altitude(self):
        route = self.route

        # intercept call to maps.googleapis.com with httpretty
        httpretty.enable()

        googleapis_url = 'https://maps.googleapis.com/maps/api/elevation/json'
        json_repsonse = self.google_elevation_json

        httpretty.register_uri(
            httpretty.GET, googleapis_url,
            content_type="application/json", body=json_repsonse,
            status=200
        )

        start_altitude = route.get_start_altitude()

        httpretty.disable()

        self.assertAlmostEqual(start_altitude.m, 448.54)

    def test_get_end_altitude(self):
        route = self.route

        # intercept call to maps.googleapis.com with httpretty
        httpretty.enable()

        googleapis_url = 'https://maps.googleapis.com/maps/api/elevation/json'
        json_repsonse = self.google_elevation_json

        httpretty.register_uri(
            httpretty.GET, googleapis_url,
            content_type="application/json", body=json_repsonse,
            status=200
        )

        end_altitude = route.get_end_altitude()

        httpretty.disable()

        self.assertAlmostEqual(end_altitude.m, 689.27)

    def test_get_distance_data_from_line_location(self):
        route = self.route

        # make the call
        point_altitude = route.get_distance_data_from_line_location(
            0.5,
            'altitude'
        )

        self.assertTrue(isinstance(point_altitude, Distance))
        self.assertAlmostEqual(point_altitude.ft, 1760.23622047244095)

    def test_get_start_and_end_places(self):
        route = self.route
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
        route = self.route
        route.save()

        url = reverse('routes:detail', args=[route.id])
        name = route.name
        start_place_name = route.start_place.name
        end_place_name = route.end_place.name

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(name in str(response.content))
        self.assertTrue(start_place_name in str(response.content))
        self.assertTrue(end_place_name in str(response.content))
