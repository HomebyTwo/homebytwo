import json
from os.path import dirname, realpath
from xml.dom import minidom

from django.test import TestCase, override_settings
from django.urls import reverse

import pytest
import responses
from garmin_uploader import api as garmin_api
from mock import patch
from pytest_django.asserts import assertContains, assertRedirects

from ...utils.factories import AthleteFactory
from ...utils.tests import create_route_with_checkpoints
from ..tasks import upload_route_to_garmin_task
from ..utils import GARMIN_ACTIVITY_TYPE_MAP

CURRENT_DIR = dirname(realpath(__file__))


def block_garmin_authentication_urls():
    """
    helper task to authenticate with the Garmin uploader blocking all calls
    """

    # get hostname
    host_name_response = '{"host": "https://connect.garmin.com"}'
    responses.add(
        responses.GET,
        garmin_api.URL_HOSTNAME,
        body=host_name_response,
        content_type="application/json",
    )

    # get login form
    get_login_body = '<input type="hidden" name="_csrf" value="CSRF" />'
    responses.add(
        responses.GET,
        garmin_api.URL_LOGIN,
        body=get_login_body,
        match_querystring=False,
    )

    # sign-in
    sign_in_body = "var response_url = 'foo?ticket=bar'"
    responses.add(
        responses.POST,
        garmin_api.URL_LOGIN,
        body=sign_in_body,
        match_querystring=False,
        adding_headers={"set-cookie": "GARMIN-SSO-GUID=foo; Domain=garmin.com; Path=/"},
    )

    # redirect to some place
    post_login = "almost there..."
    responses.add(
        responses.GET,
        garmin_api.URL_POST_LOGIN,
        body=post_login,
        match_querystring=False,
    )

    # check login
    check_login = '{"fullName": "homebytwo"}'
    responses.add(
        responses.GET,
        garmin_api.URL_PROFILE,
        body=check_login,
        content_type="application/json",
    )


def block_garmin_delete_urls(garmin_activity_id, status=200):
    # delete activity
    delete_url = (
        "https://connect.garmin.com/modern/proxy/activity-service/activity/{}".format(
            garmin_activity_id
        )
    )
    responses.add(
        responses.DELETE,
        delete_url,
        body="",
        status=status,
    )


def block_garmin_upload_urls(garmin_activity_id, route_activity_type):

    activity_url = "{}/{}".format(garmin_api.URL_ACTIVITY_BASE, garmin_activity_id)

    # upload activity
    upload_url = f"{garmin_api.URL_UPLOAD}/.gpx"
    upload_activity_response = {
        "detailedImportResult": {"successes": [{"internalId": garmin_activity_id}]}
    }
    responses.add(
        responses.POST,
        upload_url,
        body=json.dumps(upload_activity_response),
        content_type="application/json",
    )

    # update activity
    responses.add(
        responses.POST,
        activity_url,
        body="yeah!",
    )

    activity_type = GARMIN_ACTIVITY_TYPE_MAP.get(route_activity_type, "other")
    activity_type_response = [{"typeKey": activity_type}]
    responses.add(
        responses.GET,
        garmin_api.URL_ACTIVITY_TYPES,
        body=json.dumps(activity_type_response),
        content_type="application/json",
    )


@responses.activate
def intercepted_garmin_upload_task(route, athlete):
    """
    helper method to upload a route to Garmin while blocking all external calls
    """
    garmin_activity_id = route.garmin_id or 654321

    block_garmin_authentication_urls()
    block_garmin_upload_urls(garmin_activity_id, route.activity_type.name)
    block_garmin_delete_urls(garmin_activity_id)

    return upload_route_to_garmin_task(route.pk, athlete.id)


@override_settings(
    GARMIN_CONNECT_USERNAME="example@example.com",
    GARMIN_CONNECT_PASSWORD="testpassword",
    GARMIN_ACTIVITY_URL="https://example.com/garmin/{}",
)
class GPXTestCase(TestCase):
    def setUp(self):
        self.athlete = AthleteFactory(user__password="testpassword")
        self.client.login(username=self.athlete.user.username, password="testpassword")
        self.route = create_route_with_checkpoints(
            number_of_checkpoints=9, athlete=self.athlete
        )

    def test_gpx_no_start_no_end_no_checkpoints(self):
        self.route.calculate_projected_time_schedule(self.athlete.user)
        self.route.checkpoint_set.all().delete()
        self.route.start_place = None
        self.route.end_place = None

        xml_doc = minidom.parseString(self.route.get_gpx())
        waypoints = xml_doc.getElementsByTagName("wpt")
        track = xml_doc.getElementsByTagName("trk")

        self.assertEqual(len(waypoints), 0)
        self.assertEqual(len(track), 1)

    def test_gpx_success(self):
        self.route.calculate_projected_time_schedule(self.athlete.user)
        xml_doc = minidom.parseString(self.route.get_gpx())
        waypoints = xml_doc.getElementsByTagName("wpt")
        trackpoints = xml_doc.getElementsByTagName("trkpt")

        self.assertEqual(len(waypoints), self.route.places.count() + 2)
        self.assertEqual(len(trackpoints), len(self.route.data.index))

    def test_download_route_gpx_other_athlete_view(self):
        second_athlete = AthleteFactory(user__password="123456")
        self.client.login(username=second_athlete.user.username, password="123456")

        gpx_url = reverse("routes:gpx", kwargs={"pk": self.route.pk})
        response = self.client.get(gpx_url)

        assert response.status_code == 403

    def test_download_route_gpx_route_with_no_schedule(self):
        assert "schedule" not in self.route.data.columns

        response = self.client.get(reverse("routes:gpx", kwargs={"pk": self.route.pk}))
        file_content = b"".join(response.streaming_content).decode("utf-8")

        self.assertIn("<name>{}</name>".format(self.route.name), file_content)

    def test_garmin_upload_task_success(self):
        self.route.garmin_id = 123456
        self.route.save(update_fields=["garmin_id"])

        message = "Route '{route}' successfully uploaded to Garmin connect at {url}."
        route_str = str(self.route)

        response = intercepted_garmin_upload_task(self.route, self.athlete)

        self.route.refresh_from_db()
        garmin_activity_url = self.route.garmin_activity_url

        self.assertIn(
            response, message.format(route=route_str, url=garmin_activity_url)
        )

    def test_garmin_upload_task_old_route_success(self):

        assert "schedule" not in self.route.data.columns
        self.route.garmin_id = 1

        self.route.save(update_fields=["data", "garmin_id"])

        message = "Route '{route}' successfully uploaded to Garmin connect at {url}."
        route_str = str(self.route)

        response = intercepted_garmin_upload_task(self.route, self.athlete)

        self.route.refresh_from_db()
        garmin_activity_url = self.route.garmin_activity_url

        self.assertIn(
            response, message.format(route=route_str, url=garmin_activity_url)
        )

    def test_garmin_upload_other_athlete(self):
        self.route.garmin_id = 1
        self.route.save(update_fields=["garmin_id"])

        second_athlete = AthleteFactory(user__password="123456")
        self.client.login(username=second_athlete.user.username, password="123456")

        message = "Route '{route}' successfully uploaded to Garmin connect at {url}."
        route_str = str(self.route)

        response = intercepted_garmin_upload_task(self.route, second_athlete)

        self.route.refresh_from_db()
        garmin_activity_url = self.route.garmin_activity_url

        self.assertIn(
            response, message.format(route=route_str, url=garmin_activity_url)
        )

    @responses.activate
    def test_garmin_upload_failure_cannot_signin(self):
        self.route.garmin_id = 1
        self.route.save(update_fields=["garmin_id"])

        # fail auth quickly
        responses.add(
            responses.GET,
            garmin_api.URL_HOSTNAME,
            body="{}",
            content_type="application/json",
            status=500,
        )

        response = upload_route_to_garmin_task(self.route.pk, self.athlete.id)

        self.assertIn("Garmin API failure:", response)

    @responses.activate
    def test_garmin_delete_failure(self):
        self.route.garmin_id = 123456
        self.route.save(update_fields=["garmin_id"])

        block_garmin_authentication_urls()
        block_garmin_delete_urls(self.route.garmin_id, status=500)

        response = upload_route_to_garmin_task(self.route.pk, self.athlete.id)

        self.assertIn("Failed to delete activity", response)


@pytest.fixture
def gpx_route(athlete):
    return create_route_with_checkpoints(number_of_checkpoints=5, athlete=athlete)


def test_garmin_activity_url(athlete, client, gpx_route, settings):
    settings.GARMIN_ACTIVITY_URL = "https://example.com/garmin/{}"
    gpx_route.garmin_id = 123456
    gpx_route.save(update_fields=["garmin_id"])
    response = client.get(gpx_route.get_absolute_url())
    user = response.context["user"]
    assert user.has_perm(gpx_route.get_perm("garmin_upload"), gpx_route)
    assertContains(response, gpx_route.garmin_activity_url)


def test_garmin_upload_not_owner(athlete, client, gpx_route):
    gpx_route.athlete = AthleteFactory()
    gpx_route.save(update_fields=["athlete"])
    response = client.get(gpx_route.get_absolute_url("garmin_upload"))

    assert response.status_code == 403


def test_garmin_upload(athlete, client, gpx_route):
    upload_url = gpx_route.get_absolute_url("garmin_upload")
    route_url = gpx_route.get_absolute_url()

    with patch("homebytwo.routes.tasks.upload_route_to_garmin_task.delay") as mock_task:
        response = client.get(upload_url)
        assertRedirects(response, route_url)
        assert mock_task.called


def test_download_route_gpx_view(athlete, client):
    route = create_route_with_checkpoints(number_of_checkpoints=5, athlete=athlete)
    wpt_xml = '<wpt lat="{1}" lon="{0}">'
    xml_waypoints = [
        wpt_xml.format(*place.get_coords()) for place in route.places.all()
    ]
    xml_segment_name = "<name>{}</name>".format(route.name)

    url = route.get_absolute_url(action="gpx")
    response = client.get(url)
    file_content = b"".join(response.streaming_content).decode("utf-8")
    assert xml_segment_name in file_content
    for xml_waypoint in xml_waypoints:
        assert xml_waypoint in file_content
