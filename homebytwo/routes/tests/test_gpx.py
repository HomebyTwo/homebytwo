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

    def test_gpx_export_view(self):
        xml_waypoint = '<wpt lng="{}" lat="{}">'.format(*self.route.places.first().geom.transform(4326, clone=True).coords)
        xml_segment_name = "some xml content"
        xml_trkpnt = "some xml content"

        response = self.client.get(
            reverse("routes:as_gpx", kwargs={"pk": self.route.pk})
        )
        import pdb; pdb.set_trace()
        self.assertContains(response, xml_waypoint, html=True)
