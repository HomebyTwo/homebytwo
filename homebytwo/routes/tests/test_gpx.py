from xml.dom import minidom

from django.contrib.gis.geos import Point
from django.test import TestCase
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

    def test_gpx_no_checkpoint(self):
        self.route.checkpoint_set.all().delete()
        xml_doc = minidom.parseString(self.route.get_gpx())
        waypoints = xml_doc.getElementsByTagName("wpt")
        track = xml_doc.getElementsByTagName("trk")

        self.assertEqual(len(waypoints), 0)
        self.assertEqual(len(track), 1)

    def test_gpx_success(self):
        xml_doc = minidom.parseString(self.route.get_gpx())
        waypoints = xml_doc.getElementsByTagName("wpt")

        self.assertEqual(len(waypoints), self.route.places.count())

    def test_download_route_gpx_view(self):
        xml_waypoints = [
            '<wpt lat="{1}" lon="{0}">'.format(
                *place.geom.transform(4326, clone=True).coords
            )
            for place in self.route.places.all()
        ]

        xml_segment_name = "<name>{}</name>".format(self.route.name)
        xml_trkpnt = '<trkpt lat="{1}" lon="{0}">'.format(
            *self.route.geom.transform(4326, clone=True).coords[5]
        )

        url = reverse("routes:as_gpx", kwargs={"pk": self.route.pk})
        response = self.client.get(url)
        file_content = b"".join(response.streaming_content).decode("utf-8")

        for xml_waypoint in xml_waypoints:
            self.assertIn(xml_waypoint, file_content)
        self.assertIn(xml_segment_name, file_content)
        self.assertIn(xml_trkpnt, file_content)
