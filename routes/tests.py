from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse

from django.contrib.gis.geos import GEOSGeometry, fromstr
from django.contrib.gis.measure import Distance

from .models import Place, Route
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
        user = User.objects.create_user('testuser', 'test@test.com', 'test')

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
        line = fromstr(
            'LINESTRING(612190.0 612190.0, 615424.648017 129784.662852)',
            srid=21781
        )

        place1 = Place(**self.data)
        place1.geom = fromstr('POINT(615424 129744.0)', srid=21781)
        place1.save()

        place2 = Place(**self.data)
        place2.geom = fromstr('POINT(4.0 4.0)', srid=21781)
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
    GOOGLEMAPS_API_KEY='AIzabcdefghijklmnopqrstuvwxyz0123456789',
)
class RouteTestCase(TestCase):

    def setUp(self):

        route_geojson = ('{"type": "LineString", "coordinates": [[612190.0, 129403.0], [615424.648017, 129784.662852]]}')
        # Add user to the test database
        user = User.objects.create_user('testuser', 'test@test.com', 'test')

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
            user=user,
            totalup=1234,
            totaldown=4321,
            length=12345,
            geom=GEOSGeometry(route_geojson, srid=21781),
            start_place=start_place,
            end_place=end_place,
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

        self.assertAlmostEqual(start_altitude.m, 123.456)

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

        self.assertAlmostEqual(end_altitude.m, 123.456)

    def test_get_point_altitude_along_track_success(self, location=0):
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

        # make the call
        point_altitude = route.get_point_altitude_along_track(0.5)

        httpretty.disable()

        self.assertAlmostEqual(point_altitude.ft, 405.03937007874015)

    def test_get_point_altitude_along_track_error(self, location=0):
        route = self.route

        # intercept call to maps.googleapis.com with httpretty
        httpretty.enable()

        googleapis_url = 'https://maps.googleapis.com/maps/api/elevation/json'
        html_repsonse = '<h1>Server Error</h1>'

        httpretty.register_uri(
            httpretty.GET, googleapis_url,
            content_type="text/html", body=html_repsonse,
            status=500
        )
        point_altitude = route.get_point_altitude_along_track(0.5)

        httpretty.disable()

        self.assertAlmostEqual(point_altitude.ft, 405.03937007874015)

    def test_get_start_and_end_places(self):
        route = self.route
        start_place = route.get_closest_places_along_track()[0]
        end_place = route.get_closest_places_along_track(1)[0]

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
        start_place = route.start_place.name
        end_place = route.end_place.name

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(name in str(response.content))
        self.assertTrue(start_place in str(response.content))
        self.assertTrue(end_place in str(response.content))
