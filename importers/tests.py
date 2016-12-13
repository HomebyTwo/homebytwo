from django.test import TestCase
from unittest import skip

from django.contrib.auth.models import User
from importers.models import StravaRoute

from django.contrib.gis.geos import LineString


class StravaRouteTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='tester', email='test@homebytwo.ch', password='top_test')

        StravaRoute.objects.create(
            strava_route_id=1234567,
            name='Test Route',
            totalup='12345',
            totaldown='0',
            length='12345',
            geom=LineString((0, 0), (0, 12345)),
            description='Test Description',
            type=1,
            sub_type=1,
            user=self.user,
            timestamp='',
        )

    @skip('Not ready for testing')
    def test_strava_route_timestamp_is_set_to_now(self):
        """timestamp is set to now by default"""
        route = StravaRoute.objects.get(strava_route_id=1234567)
        self.assertEqual(route.timestamp, '')
