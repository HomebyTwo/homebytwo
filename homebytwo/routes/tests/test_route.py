from datetime import timedelta
from os import urandom
from pathlib import Path
from unittest import skip
from uuid import uuid4

from django.conf import settings
from django.contrib.gis.geos import LineString, Point
from django.contrib.gis.measure import Distance
from django.core.management import CommandError, call_command
from django.forms.models import model_to_dict
from django.test import TestCase, override_settings
from django.urls import resolve, reverse
from django.utils.six import StringIO

import pytest
import responses
from pandas import DataFrame

from ...utils.factories import AthleteFactory
from ...utils.tests import read_data
from ..fields import DataFrameField
from ..forms import RouteForm
from ..models import Route
from ..templatetags.duration import base_round, display_timedelta, nice_repr
from .factories import ActivityPerformanceFactory, PlaceFactory, RouteFactory

CURRENT_DIR = Path(__file__).resolve().parent


@override_settings(
    SWITZERLAND_MOBILITY_ROUTE_DATA_URL="https://example.com/track/%d/show",
    SWITZERLAND_MOBILITY_ROUTE_URL="https://example.com/?trackId=%d",
)
class RouteTestCase(TestCase):
    def setUp(self):
        self.athlete = AthleteFactory(user__password="test_password")
        self.client.login(username=self.athlete.user.username, password="test_password")

    #########
    # Model #
    #########

    def test_str(self):
        route = RouteFactory()
        self.assertEqual(
            str(route),
            "{activity_type}: {name}".format(
                activity_type=str(route.activity_type), name=route.name
            ),
        )

    def test_display_url(self):
        route = RouteFactory()
        self.assertEqual(route.display_url, route.get_absolute_url())

        match = resolve(route.edit_url)
        assert match.app_name == "routes"
        assert match.url_name == "edit"

        match = resolve(route.update_url)
        assert match.app_name == "routes"
        assert match.url_name == "update"

        match = resolve(route.delete_url)
        assert match.app_name == "routes"
        assert match.url_name == "delete"

        match = resolve(route.gpx_url)
        assert match.app_name == "routes"
        assert match.url_name == "gpx"

        match = resolve(route.import_url)
        assert match.url_name == "import_route"

    def test_get_total_distance(self):
        route = RouteFactory.build(total_distance=12345)
        total_distance = route.get_total_distance()

        self.assertTrue(isinstance(total_distance, Distance))
        self.assertEqual(total_distance.km, 12.345)

    def test_get_total_elevation_gain(self):
        route = RouteFactory.build(total_elevation_gain=1234)
        total_elevation_gain = route.get_total_elevation_gain()

        self.assertTrue(isinstance(total_elevation_gain, Distance))
        self.assertAlmostEqual(total_elevation_gain.ft, 4048.556430446194)

    def test_get_total_elevation_loss(self):
        route = RouteFactory.build(total_elevation_loss=4321)
        total_elevation_loss = route.get_total_elevation_loss()

        self.assertTrue(isinstance(total_elevation_loss, Distance))
        self.assertAlmostEqual(total_elevation_loss.m, 4321)

    def test_get_start_altitude(self):
        data = DataFrame(
            [[0, 0], [1234, 1000]],
            columns=["altitude", "distance"],
        )
        route = RouteFactory.build(
            data=data,
            total_distance=1000,
            geom=LineString(((500000.0, 300000.0), (501000.0, 300000.0)), srid=21781),
        )
        start_altitude = route.get_start_altitude()
        end_altitude = route.get_end_altitude()

        self.assertAlmostEqual(start_altitude.m, 0)
        self.assertAlmostEqual(end_altitude.m, 1234)

    def test_get_distance_data(self):
        data = DataFrame(
            [[0, 0], [1000, 1000]],
            columns=["altitude", "distance"],
        )
        route = RouteFactory.build(data=data, total_distance=1000)

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
            geom=Point(x=565586.0225000009, y=112197.4462499991, srid=21781),
        )
        PlaceFactory(
            name="Noudane Dessus",
            geom=Point(x=565091.2349999994, y=111464.0387500003, srid=21781),
        )
        PlaceFactory(
            name="Col du Jorat",
            geom=Point(x=564989.3350000009, y=111080.0012499988, srid=21781),
        )
        PlaceFactory(
            name="Saut Peca",
            geom=Point(x=564026.3412499987, y=110762.4175000004, srid=21781),
        )
        PlaceFactory(
            name="Haute Cime",
            geom=Point(x=560188.0975000001, y=112309.0137500018, srid=21781),
        )
        PlaceFactory(
            name="Col des Paresseux",
            geom=Point(x=560211.875, y=112011.8737500012, srid=21781),
        )
        PlaceFactory(
            name="Col de Susanfe",
            geom=Point(x=559944.7375000007, y=110888.6424999982, srid=21781),
        )
        PlaceFactory(
            name="Cabane de Susanfe CAS",
            geom=Point(x=558230.2575000003, y=109914.8912499994, srid=21781),
        )
        PlaceFactory(
            name="Pas d'Encel",
            geom=Point(x=556894.5662500001, y=110045.9137500003, srid=21781),
        )
        PlaceFactory(
            name="Refuge de Bonaveau",
            geom=Point(x=555775.7837500013, y=111198.6625000015, srid=21781),
        )

        checkpoints = route.find_possible_checkpoints(max_distance=100)

        self.assertEqual(len(checkpoints), 12)
        for checkpoint in checkpoints:
            self.assertNotEqual(checkpoint.line_location, 0)
            self.assertNotEqual(checkpoint.line_location, 1)

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

    def test_get_route_details(self):
        route = RouteFactory()

        with self.assertRaises(NotImplementedError):
            route.get_route_details()

    def test_get_route_data(self):
        route = RouteFactory()

        with self.assertRaises(NotImplementedError):
            route.get_route_data()

    def test_get_or_stub_new(self):
        source_id = 123456789
        route, update = Route.get_or_stub(source_id=source_id, athlete=self.athlete)

        assert route.data_source == "homebytwo"
        assert route.source_id == source_id
        assert route.athlete == self.athlete
        assert not update
        assert not route.pk

    def test_get_or_stub_existing(self):
        existing_route = RouteFactory(athlete=self.athlete)
        retrieved_route, update = Route.get_or_stub(
            source_id=existing_route.source_id, athlete=self.athlete
        )

        assert retrieved_route.data_source == "homebytwo"
        assert retrieved_route.source_id == existing_route.source_id
        assert retrieved_route.athlete == self.athlete
        assert update
        assert retrieved_route.pk

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

    def test_route_delete_404(self):
        url = "routes/0/delete/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_view_route_success_owner(self):
        route = RouteFactory(athlete=self.athlete)
        url = reverse("routes:route", args=[route.id])
        route_name = route.name
        start_place_name = route.start_place.name
        end_place_name = route.end_place.name
        edit_url = reverse("routes:edit", args=[route.id])
        edit_button = (
            '<a class="btn btn--secondary btn--block" href="{href}">{text}</a>'.format(
                href=edit_url, text="Edit Route"
            )
        )

        response = self.client.get(url)

        self.assertContains(response, route_name)
        self.assertContains(response, start_place_name)
        self.assertContains(response, end_place_name)
        self.assertContains(response, edit_button, html=True)

    def test_view_route_success_not_owner(self):
        route = RouteFactory()
        url = reverse("routes:route", args=[route.id])
        edit_url = reverse("routes:edit", args=[route.id])

        response = self.client.get(url)
        response_content = response.content.decode("UTF-8")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(edit_url, response_content)

    def test_view_route_success_not_logged_in(self):
        route = RouteFactory()
        url = reverse("routes:route", args=[route.id])
        edit_url = reverse("routes:edit", args=[route.id])
        route_name = route.name

        self.client.logout()
        response = self.client.get(url)
        response_content = response.content.decode("UTF-8")

        self.assertContains(response, route_name)
        self.assertNotIn(edit_url, response_content)

    def test_view_route_success_no_start_place(self):
        route = RouteFactory(start_place=None)
        url = reverse("routes:route", args=[route.id])
        route_name = route.name
        end_place_name = route.end_place.name

        response = self.client.get(url)

        self.assertContains(response, route_name)
        self.assertContains(response, end_place_name)

    def test_view_route_success_no_end_place(self):
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
        post_data = {
            "name": route.name,
            "activity_type": 2,
        }

        response = self.client.post(url, post_data)
        redirect_url = reverse("routes:route", args=[route.id])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_post_route_remove_checkpoints(self):
        route = RouteFactory(athlete=self.athlete)

        # checkpoints
        number_of_checkpoints = 20
        checkpoints_data = []

        for index in range(1, number_of_checkpoints + 1):
            line_location = index / (number_of_checkpoints + 1)
            place = PlaceFactory(
                geom=Point(
                    *route.geom.coords[int(route.geom.num_coords * line_location)]
                )
            )
            route.places.add(place, through_defaults={"line_location": line_location})
            checkpoints_data.append("_".join([str(place.id), str(line_location)]))

        route_data = model_to_dict(route)
        post_data = {
            key: value
            for key, value in route_data.items()
            if key in RouteForm.Meta.fields
        }

        post_data["checkpoints"] = checkpoints_data[: number_of_checkpoints - 2]

        # post
        url = reverse("routes:edit", args=[route.id])
        self.client.post(url, post_data)
        self.assertEqual(route.checkpoint_set.count(), number_of_checkpoints - 2)

    @skip  # until rules is implemented
    def test_post_route_edit_not_owner(self):
        route = RouteFactory(athlete=AthleteFactory())
        url = reverse("routes:edit", args=[route.id])

        post_data = {
            "name": route.name,
            "description": route.description,
        }

        response = self.client.post(url, post_data)

        self.assertEqual(response.status_code, 401)

    @responses.activate
    def test_get_route_update_form(self):
        route = RouteFactory(athlete=self.athlete, data_source="switzerland_mobility")
        url = reverse("routes:update", args=[route.id])

        remote_url = settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL % int(route.source_id)
        json_response = read_data(file="2191833_show.json", dir_path=CURRENT_DIR)

        responses.add(
            responses.GET,
            remote_url,
            content_type="application/json",
            body=json_response,
            status=200,
        )

        response = self.client.get(url)

        remote_route_name = "Haute Cime"
        content = '<h2 class="text-center mrgb0">{}</h2>'.format(remote_route_name)
        self.assertContains(response, content, html=True)

    @responses.activate
    def test_post_route_update_form(self):
        route = RouteFactory(athlete=self.athlete, data_source="switzerland_mobility")
        url = reverse("routes:update", args=[route.id])
        post_data = {
            "name": route.name,
            "activity_type": route.activity_type.id,
        }
        remote_url = settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL % int(route.source_id)
        json_response = read_data(file="2191833_show.json", dir_path=CURRENT_DIR)

        responses.add(
            responses.GET,
            remote_url,
            content_type="application/json",
            body=json_response,
            status=200,
        )

        response = self.client.post(url, post_data)

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
        route = RouteFactory(athlete=self.athlete, start_place=None, end_place=None)

        # checkpoints
        number_of_checkpoints = 5

        for index in range(1, number_of_checkpoints + 1):
            line_location = index / (number_of_checkpoints + 1)
            PlaceFactory(
                geom=Point(
                    *route.geom.coords[int(route.geom.num_coords * line_location)],
                    srid=21781
                )
            )

        url = reverse("routes:checkpoints_list", args=[route.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["checkpoints"]), number_of_checkpoints)

    #######################
    # Management Commands #
    #######################

    def test_cleanup_hdf5_files_no_data(self):
        # No files in data directory
        out = StringIO()

        call_command("cleanup_hdf5_files", "--dry-run", stdout=out)
        self.assertIn("No files to delete.", out.getvalue())

        call_command("cleanup_hdf5_files", stdout=out)
        self.assertIn("No files to delete.", out.getvalue())

    def test_cleanup_hdf5_files_routes(self):
        out = StringIO()

        # five routes no extra files
        RouteFactory.create_batch(5)

        call_command("cleanup_hdf5_files", "--dry-run", stdout=out)
        self.assertIn("No files to delete.", out.getvalue())

        call_command("cleanup_hdf5_files", stdout=out)
        self.assertIn("No files to delete.", out.getvalue())

    def test_cleanup_hdf5_files_delete_trash(self):
        out = StringIO()
        data_dir = Path(settings.MEDIA_ROOT, "data")
        data_dir.mkdir(parents=True, exist_ok=True)

        for i in range(5):
            filename = uuid4().hex + ".h5"
            full_path = data_dir / filename
            with full_path.open(mode="wb") as file_:
                file_.write(urandom(64))

        call_command("cleanup_hdf5_files", "--dry-run", stdout=out)
        self.assertIn(
            "Clean-up command would delete 5 and keep 0 files.", out.getvalue()
        )

        call_command("cleanup_hdf5_files", stdout=out)
        self.assertIn("Successfully deleted 5 files.", out.getvalue())

    def test_cleanup_hdf5_files_missing_route_file(self):
        out = StringIO()

        # 5 routes, include one to use the filepath
        route, *_ = RouteFactory.create_batch(5)
        field = DataFrameField()
        full_path = field.storage.path(route.data.filepath)
        data_dir = Path(full_path).parent.resolve()

        # delete one route file
        file_to_delete = list(data_dir.glob("*"))[0]
        (data_dir / file_to_delete).unlink()

        # add one random file
        filename = uuid4().hex + ".h5"
        full_path = data_dir / filename
        with full_path.open(mode="wb") as file_:
            file_.write(urandom(64))

        call_command("cleanup_hdf5_files", "--dry-run", stdout=out)
        self.assertIn(
            "Clean-up command would delete 1 and keep 4 files.", out.getvalue()
        )
        self.assertIn("1 missing file(s):", out.getvalue())

        call_command("cleanup_hdf5_files", stdout=out)
        self.assertIn("Successfully deleted 1 files.", out.getvalue())
        self.assertIn("1 missing file(s):", out.getvalue())

    def test_cleanup_hdf5_files_directory_as_file(self):
        out = StringIO()

        # 1 route
        route = RouteFactory()
        field = DataFrameField()
        full_path = field.storage.path(route.data.filepath)
        data_dir = Path(full_path).parent.resolve()

        # add one random directory with .h5 extension
        dirname = "dir.h5"
        full_path = data_dir / dirname
        Path(full_path).mkdir(parents=True, exist_ok=True)

        with self.assertRaises(CommandError):
            call_command("cleanup_hdf5_files", stdout=out)


def test_calculate_step_distances():
    data = DataFrame(
        {
            "altitude": [0, 1, 2, 1, 0],
            "distance": [0, 1, 2, 3, 4],
        }
    )
    geom = LineString((0, 0), (0, 1), (0, 2), (0, 3), (0, 4))
    route = RouteFactory.build(data=data, geom=geom)
    route.calculate_step_distances(min_distance=1, commit=False)

    assert route.data.columns.to_list() == ["altitude", "distance", "step_distance"]
    step_distance = [0.0, 1.0, 1.0, 1.0, 1.0]
    assert route.data.step_distance.to_list() == step_distance


def test_calculate_step_distances_bad_values():
    data = DataFrame(
        {
            "altitude": [0, 1, 2, 1, 0],
            "distance": [0, 0.5, 1, 2, 3],
        }
    )
    geom = LineString([(lng, 0) for lng in data.distance.to_list()])
    route = RouteFactory.build(data=data, geom=geom)
    route.calculate_step_distances(min_distance=1, commit=False)

    step_distance = [0.0, 2.0, 1.0]
    assert route.data.step_distance.to_list() == step_distance
    assert len(route.data.step_distance) == len(route.geom)


def test_calculate_step_distances_commit(athlete):
    data = DataFrame(
        {
            "altitude": [0, 1, 2, 1, 0],
            "distance": [0, 1, 2, 3, 4],
        }
    )
    geom = LineString([(lng, 0) for lng in data.distance.to_list()])
    route = RouteFactory(name="step_distance", data=data, geom=geom, athlete=athlete)
    route.calculate_step_distances(min_distance=1, commit=True)

    saved_route = Route.objects.get(name="step_distance", athlete=athlete)

    step_distance = [0.0, 1.0, 1.0, 1.0, 1.0]
    assert saved_route.data.step_distance.to_list() == step_distance
    assert len(saved_route.data.step_distance) == len(saved_route.geom)


def test_calculate_distances_impossible():
    data = DataFrame(
        {
            "altitude": [0, 1, 2, 1, 0],
            "distance": [0, 0.5, 1, 1.5, 2],
        }
    )
    geom = LineString([(lng, 0) for lng in data.distance.to_list()])
    route = RouteFactory.build(data=data, geom=geom)
    with pytest.raises(ValueError):
        route.calculate_step_distances(min_distance=1, commit=False)


def test_calculate_gradients():
    data = DataFrame(
        {
            "altitude": [0, 1, 2, 3, 2, 1, 0],
            "distance": [0, 1, 2, 3, 4, 5, 6],
        }
    )
    geom = LineString((0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (0, 6))
    route = RouteFactory.build(data=data, geom=geom)
    route.calculate_gradients(max_gradient=100, commit=False)

    assert route.data.columns.to_list() == ["altitude", "distance", "gradient"]
    gradients = [0.0, 100.0, 100.0, 100.0, -100.0, -100.0, -100.0]
    assert route.data.gradient.to_list() == gradients


def test_calculate_gradients_bad_values():
    geom = LineString((0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (0, 6))
    data = DataFrame(
        {
            "altitude": [0, 1, 3, 3, 1, 1, 0],
            "distance": [0, 1, 2, 3, 4, 5, 6],
        }
    )
    route = RouteFactory.build(data=data, geom=geom)
    route.calculate_gradients(max_gradient=100, commit=False)

    gradients = [0.0, 100.0, 100.0, -100.0, -100.0]
    assert route.data.gradient.to_list() == gradients
    assert len(route.data.gradient) == len(route.geom)


def test_calculate_gradients_commit(athlete):
    geom = LineString((0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (0, 6))
    data = DataFrame(
        {
            "altitude": [0, 1, 2, 3, 1, 1, 0],
            "distance": [0, 1, 2, 3, 4, 5, 6],
        }
    )
    route = RouteFactory(name="gradient", data=data, geom=geom, athlete=athlete)
    route.calculate_gradients(max_gradient=100, commit=True)

    gradients = [0.0, 100.0, 100.0, 100.0, -100.0, -100.0]
    saved_route = Route.objects.get(name="gradient", athlete=athlete)
    assert saved_route.data.gradient.to_list() == gradients
    assert len(saved_route.data.gradient) == len(saved_route.geom)


def test_calculate_gradients_impossible():
    geom = LineString((0, 0), (0, 1), (0, 2), (0, 3), (0, 4))
    data = DataFrame(
        {
            "altitude": [0, 2, 4, 6, 10],
            "distance": [0, 1, 2, 3, 4],
        }
    )
    route = RouteFactory.build(data=data, geom=geom)
    with pytest.raises(ValueError):
        route.calculate_gradients(max_gradient=100, commit=False)


def test_add_distance_and_elevation_totals():
    route = RouteFactory.build(total_distance=1000, total_elevation_gain=500)
    route.add_distance_and_elevation_totals(commit=False)
    assert route.data.total_distance.unique() == [route.total_distance]
    assert route.data.total_elevation_gain.unique() == [route.total_elevation_gain]
    assert route.data.columns.to_list() == [
        "altitude",
        "distance",
        "total_distance",
        "total_elevation_gain",
    ]


def test_add_distance_and_elevation_totals_commit(athlete):
    route = RouteFactory(
        name="totals", total_distance=1000, total_elevation_gain=500, athlete=athlete
    )
    route.add_distance_and_elevation_totals(commit=True)

    saved_route = Route.objects.get(name="totals", athlete=athlete)
    assert route.data.columns.to_list() == [
        "altitude",
        "distance",
        "total_distance",
        "total_elevation_gain",
    ]
    assert saved_route.data.total_distance.unique() == [saved_route.total_distance]
    assert saved_route.data.total_elevation_gain.unique() == [
        saved_route.total_elevation_gain
    ]


def test_calculate_cumulative_elevation_differences():
    data = DataFrame(
        {
            "distance": list(range(10)),
            "altitude": [0, 1, 2, 1, 2, 3, 2, 1, 0, 1],
        }
    )
    route = RouteFactory.build(data=data)
    route.calculate_cumulative_elevation_differences(commit=False)
    cumulative_elevation_gain = [0, 1, 2, 2, 3, 4, 4, 4, 4, 5]
    cumulative_elevation_loss = [0, 0, 0, -1, -1, -1, -2, -3, -4, -4]
    assert route.data.columns.to_list() == [
        "distance",
        "altitude",
        "cumulative_elevation_gain",
        "cumulative_elevation_loss",
    ]
    assert route.data.cumulative_elevation_gain.to_list() == cumulative_elevation_gain
    assert route.data.cumulative_elevation_loss.to_list() == cumulative_elevation_loss


def test_calculate_cumulative_elevation_differences_commit(athlete):
    data = DataFrame(
        {
            "distance": list(range(5)),
            "altitude": [0, 1, 2, 1, 0],
        }
    )
    route = RouteFactory(name="cumulative", data=data, athlete=athlete)
    route.calculate_cumulative_elevation_differences(commit=True)

    saved_route = Route.objects.get(name="cumulative", athlete=athlete)
    assert saved_route.data.columns.to_list() == [
        "distance",
        "altitude",
        "cumulative_elevation_gain",
        "cumulative_elevation_loss",
    ]
    assert saved_route.data.cumulative_elevation_gain.to_list() == [0, 1, 2, 2, 2]
    assert saved_route.data.cumulative_elevation_loss.to_list() == [0, 0, 0, -1, -2]


def test_update_permanent_track_data(athlete):
    data = DataFrame(
        {
            "distance": list(range(100)),
            "altitude": list(range(100)),
        }
    )
    geom = LineString([(lng, 0) for lng in data.distance.to_list()])
    route = RouteFactory(name="permanent", athlete=athlete, data=data, geom=geom)
    route.update_permanent_track_data(min_step_distance=1, max_gradient=100)

    saved_route = Route.objects.get(name="permanent", athlete=athlete)

    assert saved_route.data.columns.to_list() == [
        "distance",
        "altitude",
        "step_distance",
        "gradient",
        "cumulative_elevation_gain",
        "cumulative_elevation_loss",
        "total_distance",
        "total_elevation_gain",
    ]

    assert len(saved_route.data.distance) == len(saved_route.geom)


def test_update_permanent_track_data_bad_route():
    data = DataFrame(
        {
            "distance": list(range(10)),
            "altitude": list(range(10)),
        }
    )
    geom = LineString([(lng, 0) for lng in range(20)])
    route = RouteFactory.build(data=data, geom=geom)
    with pytest.raises(ValueError):
        route.update_permanent_track_data(commit=False)


def test_calculate_projected_time_schedule(athlete):
    route = RouteFactory()
    activity_performance = ActivityPerformanceFactory(
        athlete=athlete, activity_type=route.activity_type
    )

    route.calculate_projected_time_schedule(
        user=athlete.user,
        gear=activity_performance.gear_categories[0],
        workout_type=activity_performance.workout_type_categories[-1],
    )

    assert "gear" in route.data.columns and "workout_type" in route.data.columns
    assert "pace" in route.data.columns and "schedule" in route.data.columns


def test_calculate_projected_time_schedule_total_time(athlete):
    route = RouteFactory()

    route.calculate_projected_time_schedule(athlete.user)
    default_total_time = route.get_data(1, "schedule")

    ActivityPerformanceFactory(
        athlete=athlete,
        activity_type=route.activity_type,
        flat_parameter=route.activity_type.flat_parameter / 2
    )

    route.calculate_projected_time_schedule(athlete.user)
    athlete_total_time = route.get_data(1, "schedule")

    assert default_total_time > athlete_total_time


def test_schedule_display():
    duration = timedelta(seconds=30, minutes=1, hours=6)
    assert nice_repr(duration) == "6 hours 1 minute 30 seconds"

    duration = timedelta(seconds=0)
    assert nice_repr(duration) == "0 seconds"

    duration = timedelta(seconds=30, minutes=2, hours=2)
    assert nice_repr(duration, display_format="hike") == "2 h 5 min"

    duration = timedelta(seconds=45, minutes=57, hours=2)
    assert nice_repr(duration, display_format="hike") == "3 h"

    duration = timedelta(seconds=30, minutes=2, hours=6)
    assert nice_repr(duration, display_format="hike") == "6 h"


def test_display_timedelta():
    assert display_timedelta(None) is None
    assert display_timedelta(0) == "0 seconds"
    with pytest.raises(TypeError):
        display_timedelta("bad_value")


def test_base_round():
    values = [0, 3, 4.85, 12, -7]
    rounded = [base_round(value) for value in values]

    assert rounded == [0, 5, 5, 10, -5]
