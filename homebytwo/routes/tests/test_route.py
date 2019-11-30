from datetime import timedelta
from os import listdir, makedirs, remove, urandom
from os.path import dirname, exists, join, realpath
from shutil import rmtree
from tempfile import mkdtemp
from unittest import skip
from uuid import uuid4

from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.measure import Distance
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.six import StringIO

import httpretty
from pandas import DataFrame

from ...utils.factories import AthleteFactory, UserFactory
from ...utils.tests import open_data, read_data
from ..models import ActivityPerformance
from ..templatetags.duration import baseround, nice_repr
from .factories import ActivityTypeFactory, PlaceFactory, RouteFactory

CURRENT_DIR = dirname(realpath(__file__))


@override_settings(
    SWITZERLAND_MOBILITY_ROUTE_DATA_URL="https://example.com/track/%d/show",
    SWITZERLAND_MOBILITY_ROUTE_URL="https://example.com/?trackId=%d"
)
class RouteTestCase(TestCase):
    def setUp(self):
        self.athlete = AthleteFactory(user__password="testpassword")
        self.client.login(username=self.athlete.user.username, password="testpassword")

    #########
    # Model #
    #########

    def test_str(self):
        route = RouteFactory()
        self.assertEqual(str(route), "Route: {}".format(route.name))

    def test_display_url(self):
        route = RouteFactory()
        self.assertEqual(route.display_url, route.get_absolute_url())

    def test_get_length(self):
        route = RouteFactory.build(length=12345)
        length = route.get_length()

        self.assertTrue(isinstance(length, Distance))
        self.assertEqual(length.km, 12.345)

    def test_get_totalup(self):
        route = RouteFactory.build(totalup=1234)
        totalup = route.get_totalup()

        self.assertTrue(isinstance(totalup, Distance))
        self.assertAlmostEqual(totalup.ft, 4048.556430446194)

    def test_get_totaldown(self):
        route = RouteFactory.build(totaldown=4321)
        totaldown = route.get_totaldown()

        self.assertTrue(isinstance(totaldown, Distance))
        self.assertAlmostEqual(totaldown.m, 4321)

    def test_get_start_altitude(self):
        data = DataFrame(
            [[0, 0, 0, 0], [1000, 0, 1234, 1000]],
            columns=["lat", "lng", "altitude", "length"],
        )
        route = RouteFactory.build(data=data)
        start_altitude = route.get_start_altitude()

        self.assertAlmostEqual(start_altitude.m, 0)

        route.data = None
        end_altitude = route.get_end_altitude()
        self.assertEqual(end_altitude, None)

    def test_get_end_altitude(self):
        data = DataFrame(
            [[0, 0, 0, 0], [600000, 0, 1234, 600000]],
            columns=["lat", "lng", "altitude", "length"],
        )
        route = RouteFactory.build(data=data, length=600000)

        end_altitude = route.get_end_altitude()

        self.assertAlmostEqual(end_altitude.m, 1234)

        route.data = None
        end_altitude = route.get_end_altitude()
        self.assertEqual(end_altitude, None)

    def test_get_start_point(self):
        route = RouteFactory.build()
        start_point = route.get_start_point()

        self.assertIsInstance(start_point, GEOSGeometry)

    def test_get_distance_data(self):
        data = DataFrame(
            [[0, 0, 0, 0], [707.106781187, 707.106781187, 1000, 1000]],
            columns=["lat", "lng", "altitude", "length"],
        )
        route = RouteFactory.build(data=data, length=1000)

        # make the call
        point_altitude = route.get_distance_data(0.5, "altitude")

        self.assertTrue(isinstance(point_altitude, Distance))
        self.assertAlmostEqual(point_altitude.m, 500)

    def test_get_start_and_end_places(self):
        route = RouteFactory.build()
        PlaceFactory(name="Start_Place", geom="POINT(%s %s)" % route.geom[0])
        PlaceFactory(name="End_Place", geom="POINT(%s %s)" % route.geom[-1])
        start_place = route.get_closest_places_along_line()[0]
        end_place = route.get_closest_places_along_line(1)[0]

        self.assertEqual(start_place.distance_from_line.m, 0)
        self.assertEqual(start_place.name, "Start_Place")

        self.assertEqual(end_place.distance_from_line.m, 0)
        self.assertEqual(end_place.name, "End_Place")

    def test_find_additional_places(self):
        route = RouteFactory(name="Haute-Cime")

        PlaceFactory(
            name="Sur Frête",
            geom=GEOSGeometry(
                "POINT (565586.0225000009 112197.4462499991)", srid=21781
            ),
        )
        PlaceFactory(
            name="Noudane Dessus",
            geom=GEOSGeometry(
                "POINT (565091.2349999994 111464.0387500003)", srid=21781
            ),
        )
        PlaceFactory(
            name="Col du Jorat",
            geom=GEOSGeometry(
                "POINT (564989.3350000009 111080.0012499988)", srid=21781
            ),
        )
        PlaceFactory(
            name="Saut Peca",
            geom=GEOSGeometry(
                "POINT (564026.3412499987 110762.4175000004)", srid=21781
            ),
        )
        PlaceFactory(
            name="Haute Cime",
            geom=GEOSGeometry(
                "POINT (560188.0975000001 112309.0137500018)", srid=21781
            ),
        )
        PlaceFactory(
            name="Col des Paresseux",
            geom=GEOSGeometry("POINT (560211.875 112011.8737500012)", srid=21781),
        )
        PlaceFactory(
            name="Col de Susanfe",
            geom=GEOSGeometry(
                "POINT (559944.7375000007 110888.6424999982)", srid=21781
            ),
        )
        PlaceFactory(
            name="Cabane de Susanfe CAS",
            geom=GEOSGeometry(
                "POINT (558230.2575000003 109914.8912499994)", srid=21781
            ),
        )
        PlaceFactory(
            name="Pas d'Encel",
            geom=GEOSGeometry(
                "POINT (556894.5662500001 110045.9137500003)", srid=21781
            ),
        )
        PlaceFactory(
            name="Refuge de Bonaveau",
            geom=GEOSGeometry(
                "POINT (555775.7837500013 111198.6625000015)", srid=21781
            ),
        )

        checkpoints = route.find_possible_checkpoints(max_distance=100)

        self.assertEqual(len(checkpoints), 12)
        for checkpoint in checkpoints:
            self.assertNotEqual(checkpoint.line_location, 0)
            self.assertNotEqual(checkpoint.line_location, 1)

    def test_calculate_elevation_gain_distance(self):
        data = DataFrame(
            {"altitude": [0, 1, 2, 3, 2, 1, 0], "length": [0, 1, 2, 2, 3, 4, 5]}
        )

        route = RouteFactory(data=data)

        route.calculate_elevation_gain_and_distance()

        self.assertListEqual(
            list(route.data), ["altitude", "length", "distance", "gain"]
        )

        self.assertListEqual(
            list(route.data.distance), [0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.0]
        )

        self.assertListEqual(
            list(route.data.gain), [0.0, 1.0, 1.0, 1.0, -1.0, -1.0, -1.0]
        )

    def test_calculate_projected_time_schedule(self):
        activity_type = ActivityTypeFactory()

        route = RouteFactory(activity_type=activity_type)
        user = UserFactory()

        route.calculate_projected_time_schedule(user)
        total_default_time = route.get_data(1, "schedule")

        ActivityPerformance.objects.create(
            athlete=user.athlete,
            activity_type=activity_type,
            slope_squared_param=activity_type.slope_squared_param / 2,
            slope_param=activity_type.slope_param / 2,
            flat_param=activity_type.flat_param / 2,
            total_elevation_gain_param=activity_type.total_elevation_gain_param,
        )

        route.calculate_projected_time_schedule(user)
        total_user_time = route.get_data(1, "schedule")

        self.assertTrue(total_default_time > total_user_time)

    def test_schedule_display(self):
        duration = timedelta(seconds=30, minutes=1, hours=6)
        long_dspl = nice_repr(duration)
        self.assertEqual(long_dspl, "6 hours 1 minute 30 seconds")

        duration = timedelta(seconds=0)
        long_dspl = nice_repr(duration)
        self.assertEqual(long_dspl, "0 seconds")

        duration = timedelta(seconds=30, minutes=2, hours=2)
        hike_dspl = nice_repr(duration, display_format="hike")
        self.assertEqual(hike_dspl, "2 h 5 min")

        duration = timedelta(seconds=45, minutes=57, hours=2)
        hike_dspl = nice_repr(duration, display_format="hike")
        self.assertEqual(hike_dspl, "3 h")

        duration = timedelta(seconds=30, minutes=2, hours=6)
        hike_dspl = nice_repr(duration, display_format="hike")
        self.assertEqual(hike_dspl, "6 h")

    def test_base_round(self):
        values = [0, 3, 4.85, 12, -7]
        rounded = [baseround(value) for value in values]

        self.assertEqual(rounded, [0, 5, 5, 10, -5])

    @override_settings(
        STRAVA_ROUTE_URL="https://strava_route_url/%d",
        SWITZERLAND_MOBILITY_ROUTE_URL="https://switzerland_mobility_route_url/%d",
    )
    def test_source_link(self):
        route = RouteFactory(data_source="strava", source_id=777)
        source_url = "https://strava_route_url/777"
        self.assertEqual(route.source_link.url, source_url)
        self.assertEqual(route.source_link.text, "Strava")

        route = RouteFactory(data_source="switzerland_mobility", source_id=777)
        source_url = "https://switzerland_mobility_route_url/777"
        self.assertEqual(route.source_link.url, source_url)
        self.assertEqual(route.source_link.text, "Switzerland Mobility Plus")

        route = RouteFactory()
        self.assertIsNone(route.source_link)

    #########
    # Views #
    #########

    def test_import_routes_unknown_data_source(self):
        unknown_data_source_routes_url = reverse(
            "import_routes", kwargs={"data_source": "spam"}
        )
        response = self.client.get(unknown_data_source_routes_url)
        self.assertEqual(response.status_code, 404)

    def test_route_404(self):
        url = "routes/0/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_route_edit_404(self):
        url = "routes/0/edit/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_route_image_404(self):
        url = "routes/0/image/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_route_delete_404(self):
        url = "routes/0/delete/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_route_view_success_owner(self):
        route = RouteFactory(athlete=self.athlete)
        url = reverse("routes:route", args=[route.id])
        route_name = route.name
        start_place_name = route.start_place.name
        end_place_name = route.end_place.name
        edit_url = reverse("routes:edit", args=[route.id])
        edit_button = '<a href="%s">Edit Route</a>' % edit_url

        response = self.client.get(url)

        self.assertContains(response, route_name)
        self.assertContains(response, start_place_name)
        self.assertContains(response, end_place_name)
        self.assertContains(response, edit_button, html=True)

    def test_route_view_success_not_owner(self):
        route = RouteFactory()
        url = reverse("routes:route", args=[route.id])
        edit_url = reverse("routes:edit", args=[route.id])

        response = self.client.get(url)
        response_content = response.content.decode("UTF-8")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(edit_url, response_content)

    def test_route_view_success_not_logged_in(self):
        route = RouteFactory()
        url = reverse("routes:route", args=[route.id])
        edit_url = reverse("routes:edit", args=[route.id])
        route_name = route.name

        self.client.logout()
        response = self.client.get(url)
        response_content = response.content.decode("UTF-8")

        self.assertContains(response, route_name)
        self.assertNotIn(edit_url, response_content)

    def test_route_view_success_no_start_place(self):
        route = RouteFactory(start_place=None)
        url = reverse("routes:route", args=[route.id])
        route_name = route.name
        end_place_name = route.end_place.name

        response = self.client.get(url)

        self.assertContains(response, route_name)
        self.assertContains(response, end_place_name)

    def test_route_view_success_no_end_place(self):
        route = RouteFactory(end_place=None)
        url = reverse("routes:route", args=[route.id])
        route_name = route.name
        start_place_name = route.start_place.name

        response = self.client.get(url)

        self.assertContains(response, route_name)
        self.assertContains(response, start_place_name)

    def test_get_route_delete_view(self):
        route = RouteFactory()
        url = reverse("routes:delete", args=[route.id])
        response = self.client.get(url)
        content = "<h1>Delete %s</h1>" % route.name
        self.assertContains(response, content, html=True)

    def test_get_route_delete_not_logged(self):
        route = RouteFactory()
        url = reverse("routes:delete", args=[route.id])
        self.client.logout()

        response = self.client.get(url)
        redirect_url = "/login/?next=" + url

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_post_route_delete_view(self):
        route = RouteFactory()
        url = reverse("routes:delete", args=[route.id])
        post_data = {}
        response = self.client.post(url, post_data)

        redirect_url = reverse("routes:routes")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    @skip  # until rules is implemented
    def test_post_route_delete_not_owner(self):
        route = RouteFactory(athlete=AthleteFactory())
        url = reverse("routes:delete", args=[route.id])
        post_data = {}
        response = self.client.post(url, post_data)

        self.assertEqual(response.status_code, 401)

    def test_get_route_image_form(self):
        route = RouteFactory(athlete=self.athlete)
        url = reverse("routes:image", args=[route.id])
        response = self.client.get(url)

        content = "<h3>Edit image for %s</h3>" % route.name
        self.assertContains(response, content, html=True)

    def test_get_route_image_form_not_logged(self):
        route = RouteFactory(athlete=self.athlete)
        url = reverse("routes:image", args=[route.id])
        self.client.logout()

        response = self.client.get(url)
        redirect_url = "/login/?next=" + url

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_post_route_image(self):
        route = RouteFactory(athlete=self.athlete)
        url = reverse("routes:image", args=[route.id])
        with open_data("image.jpg", dir_path=CURRENT_DIR) as image:
            post_data = {"image": SimpleUploadedFile(image.name, image.read())}

        response = self.client.post(url, post_data)
        redirect_url = reverse("routes:route", args=[route.id])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    @skip  # until rules is implemented
    def test_post_route_image_not_owner(self):
        route = RouteFactory(athlete=AthleteFactory)
        url = reverse("routes:image", args=[route.id])

        with open_data("image.jpg", dir_path=CURRENT_DIR) as image:
            post_data = {"image": SimpleUploadedFile(image.name, image.read())}

        response = self.client.post(url, post_data)

        self.assertEqual(response.status_code, 401)

    def test_get_route_edit_form(self):
        route = RouteFactory(athlete=self.athlete)
        url = reverse("routes:edit", args=[route.id])
        response = self.client.get(url)
        content = '<h2 class="text-center mrgb0">{}</h2>'.format(route.name)
        self.assertContains(response, content, html=True)

    def test_get_route_edit_form_not_logged(self):
        route = RouteFactory(athlete=self.athlete)
        url = reverse("routes:edit", args=[route.id])
        self.client.logout()

        response = self.client.get(url)
        redirect_url = "/login/?next=" + url

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_post_route_edit_form(self):
        route = RouteFactory(athlete=self.athlete)
        url = reverse("routes:edit", args=[route.id])
        with open_data("image.jpg", dir_path=CURRENT_DIR) as image:
            post_data = {
                "name": route.name,
                "activity_type": route.activity_type.id,
                "description": route.description,
                "image": SimpleUploadedFile(image.name, image.read()),
            }

        response = self.client.post(url, post_data)
        redirect_url = reverse("routes:route", args=[route.id])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    @skip  # until rules is implemented
    def test_post_route_edit_not_owner(self):
        route = RouteFactory(athlete=AthleteFactory())
        url = reverse("routes:edit", args=[route.id])

        with open_data("image.jpg", dir_path=CURRENT_DIR) as image:
            post_data = {
                "name": route.name,
                "description": route.description,
                "image": SimpleUploadedFile(image.name, image.read()),
            }

        response = self.client.post(url, post_data)

        self.assertEqual(response.status_code, 401)

    def test_get_route_update_form(self):
        route = RouteFactory(athlete=self.athlete, data_source="switzerland_mobility")
        url = reverse("routes:update", args=[route.id])

        httpretty.enable(allow_net_connect=False)
        remote_url = settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL % int(route.source_id)
        json_response = read_data(file="2191833_show.json", dir_path=CURRENT_DIR)

        httpretty.register_uri(
            httpretty.GET,
            remote_url,
            content_type="application/json",
            body=json_response,
            status=200,
        )

        response = self.client.get(url)
        httpretty.disable()

        remote_route_name = "Haute Cime"
        content = '<h2 class="text-center mrgb0">{}</h2>'.format(remote_route_name)
        self.assertContains(response, content, html=True)

    def test_post_route_update_form(self):
        route = RouteFactory(athlete=self.athlete, data_source="switzerland_mobility")
        url = reverse("routes:update", args=[route.id])
        with open_data("image.jpg", dir_path=CURRENT_DIR) as image:
            post_data = {
                "name": route.name,
                "activity_type": route.activity_type.id,
                "description": route.description,
                "image": SimpleUploadedFile(image.name, image.read()),
            }
        httpretty.enable(allow_net_connect=False)
        remote_url = settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL % int(route.source_id)
        json_response = read_data(file="2191833_show.json", dir_path=CURRENT_DIR)

        httpretty.register_uri(
            httpretty.GET,
            remote_url,
            content_type="application/json",
            body=json_response,
            status=200,
        )

        response = self.client.post(url, post_data)
        httpretty.disable()

        redirect_url = reverse("routes:route", args=[route.id])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_get_checkpoints_list_empty(self):
        route = RouteFactory(athlete=self.athlete)
        url = reverse("routes:checkpoints_list", args=[route.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["checkpoints"], [])

    def test_get_checkpoints_list(self):
        route = RouteFactory(athlete=self.athlete)

        # checkpoints
        number_of_route_coordinates = len(route.geom.coords)
        PlaceFactory(
            geom="POINT ({} {})".format(
                *route.geom.coords[int(number_of_route_coordinates * 0.25)]
            )
        )
        PlaceFactory(
            geom="POINT ({} {})".format(
                *route.geom.coords[int(number_of_route_coordinates * 0.5)]
            )
        )
        PlaceFactory(
            geom="POINT ({} {})".format(
                *route.geom.coords[int(number_of_route_coordinates * 0.75)]
            )
        )

        url = reverse("routes:checkpoints_list", args=[route.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["checkpoints"]), 3)

    #######################
    # Management Commands #
    #######################

    @override_settings(MEDIA_ROOT=mkdtemp())
    def test_cleanup_route_data_no_data(self):
        # No files in data directory
        out = StringIO()
        call_command("cleanup_route_data", stdout=out)
        self.assertIn("No files to delete.", out.getvalue())
        rmtree(settings.MEDIA_ROOT, ignore_errors=True)

    @override_settings(MEDIA_ROOT=mkdtemp())
    def test_cleanup_route_data_routes(self):
        # five routes no extra files
        out = StringIO()
        RouteFactory.create_batch(5)

        call_command("cleanup_route_data", stdout=out)
        self.assertIn("No files to delete.", out.getvalue())
        rmtree(settings.MEDIA_ROOT, ignore_errors=True)

    @override_settings(MEDIA_ROOT=mkdtemp())
    def test_cleanup_route_data_delete_trash(self):
        # five random files not in DB
        data_dir = join(settings.BASE_DIR, settings.MEDIA_ROOT, "data")

        if not exists(data_dir):
            makedirs(data_dir)

        out = StringIO()
        for i in range(5):
            filename = uuid4().hex + ".h5"
            fullpath = join(data_dir, filename)
            with open(fullpath, "wb") as file_:
                file_.write(urandom(64))

        call_command("cleanup_route_data", stdout=out)
        self.assertIn("Successfully deleted 5 files.", out.getvalue())
        rmtree(settings.MEDIA_ROOT, ignore_errors=True)

    @override_settings(MEDIA_ROOT=mkdtemp())
    def test_cleanup_route_data_missing_route_file(self):
        # One deleted route data file one random file
        data_dir = join(settings.BASE_DIR, settings.MEDIA_ROOT, "data")
        out = StringIO()
        [RouteFactory() for i in range(5)]
        file_to_delete = listdir(data_dir)[0]
        remove(join(data_dir, file_to_delete))
        filename = uuid4().hex + ".h5"
        fullpath = join(data_dir, filename)
        with open(fullpath, "wb") as file_:
            file_.write(urandom(64))

        call_command("cleanup_route_data", stdout=out)
        self.assertIn("Successfully deleted 1 files.", out.getvalue())
        rmtree(settings.MEDIA_ROOT, ignore_errors=True)
