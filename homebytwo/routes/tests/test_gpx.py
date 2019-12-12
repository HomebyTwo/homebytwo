from xml.dom import minidom

from django.conf import settings
from django.contrib.gis.geos import Point
from django.test import TestCase, override_settings
from django.urls import reverse

from ...utils.factories import AthleteFactory
from .factories import PlaceFactory, RouteFactory


class GPXTestCase(TestCase):
    def setUp(self):
        self.athlete = AthleteFactory(user__password="testpassword")
        self.client.login(username=self.athlete.user.username, password="testpassword")
        self.route = RouteFactory(athlete=self.athlete)

        # add checkpoints to the route
        number_of_checkpoints = 9
        for index in range(1, number_of_checkpoints + 1):
            line_location = index / (number_of_checkpoints + 1)
            place = PlaceFactory(
                geom=Point(
                    *self.route.geom.coords[
                        int(self.route.geom.num_coords * line_location)
                    ]
                )
            )
            self.route.places.add(
                place, through_defaults={"line_location": line_location}
            )

    def test_gpx_no_strat_no_end_no_checkpoint(self):
        self.route.checkpoint_set.all().delete()
        self.route.start_place = None
        self.route.end_place = None

        xml_doc = minidom.parseString(self.route.get_gpx())
        waypoints = xml_doc.getElementsByTagName("wpt")
        track = xml_doc.getElementsByTagName("trk")

        self.assertEqual(len(waypoints), 0)
        self.assertEqual(len(track), 1)

    def test_gpx_success(self):
        xml_doc = minidom.parseString(self.route.get_gpx())
        waypoints = xml_doc.getElementsByTagName("wpt")
        trackpoints = xml_doc.getElementsByTagName("trkpt")

        self.assertEqual(len(waypoints), self.route.places.count() + 2)
        self.assertEqual(len(trackpoints), len(self.route.data.index))

    def test_download_route_gpx_view(self):
        wpt_xml = '<wpt lat="{1}" lon="{0}">'
        xml_start_place = wpt_xml.format(*self.route.start_place.get_coords())
        xml_end_place = wpt_xml.format(*self.route.end_place.get_coords())
        xml_waypoints = [
            wpt_xml.format(*place.get_coords()) for place in self.route.places.all()
        ]
        xml_segment_name = "<name>{}</name>".format(self.route.name)

        url = reverse("routes:gpx", kwargs={"pk": self.route.pk})
        response = self.client.get(url)
        file_content = b"".join(response.streaming_content).decode("utf-8")

        for xml_waypoint in xml_waypoints:
            self.assertIn(xml_waypoint, file_content)

        self.assertIn(xml_start_place, file_content)
        self.assertIn(xml_end_place, file_content)
        self.assertIn(xml_segment_name, file_content)

    @override_settings(GARMIN_ACTIVITY_URL="https://example.com/garmin/{}")
    def test_garmin_activity_url(self):
        self.route.garmin_id = 123456
        self.route.save(update_fields=["garmin_id"])
        garmin_url = settings.GARMIN_ACTIVITY_URL.format(self.route.garmin_id)

        response = self.client.get(reverse("routes:route", kwargs={"pk": self.route.id}))
        self.assertContains(response, garmin_url)
