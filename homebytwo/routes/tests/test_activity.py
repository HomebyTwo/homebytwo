import json
from copy import deepcopy
from pathlib import Path

from django.test import TestCase, override_settings
from django.urls import reverse

import responses
from mock import patch
from pandas import DataFrame

from ...importers.exceptions import StravaMissingCredentials
from ...utils.factories import AthleteFactory, UserFactory
from ...utils.tests import read_data
from ..fields import DataFrameField
from ..models import Activity, Gear, WebhookTransaction
from ..models.activity import are_streams_valid, is_activity_supported
from ..tasks import import_strava_activities_task
from .factories import ActivityFactory, ActivityTypeFactory, GearFactory

CURRENT_DIR = Path(__file__).resolve().parent

STRAVA_BASE_URL = "https://www.strava.com/api/v3"
ACTIVITIES_URL = STRAVA_BASE_URL + "/athlete/activities"
ACTIVITY_URL = STRAVA_BASE_URL + "/activities/{}"
STREAM_TYPES = ["time", "altitude", "distance", "moving"]
STREAMS_URL = ACTIVITY_URL + "/streams/" + ",".join(STREAM_TYPES)

PROCESSED = WebhookTransaction.PROCESSED
UNPROCESSED = WebhookTransaction.UNPROCESSED
SKIPPED = WebhookTransaction.SKIPPED
ERROR = WebhookTransaction.ERROR


class ActivityTestCase(TestCase):
    def setUp(self):
        self.athlete = AthleteFactory(user__password="test_password")
        self.client.login(username=self.athlete.user.username, password="test_password")

    def load_strava_activity_from_json(self, file):
        """
        helper to turn Strava API json results into stravalib client objects
        """
        strava_activity_json = read_data(file, dir_path=CURRENT_DIR)
        strava_activity_dict = json.loads(strava_activity_json)
        strava_activity_id = strava_activity_dict["id"]

        # intercept API call and return local json instead
        activity_url = ACTIVITY_URL.format(strava_activity_id)
        responses.add(
            responses.GET,
            activity_url,
            content_type="application/json",
            body=strava_activity_json,
            status=200,
        )

        # intercepted call to the API
        return self.athlete.strava_client.get_activity(strava_activity_id)

    def test_no_strava_token(self):
        """
        Logged-in user with no Strava auth connected, i.e. from createsuperuser
        """

        non_strava_user = UserFactory(password="test_password", social_auth=None)
        self.client.login(username=non_strava_user.username, password="test_password")

        url = reverse("routes:import_activities")

        with self.assertRaises(StravaMissingCredentials):
            self.client.get(url)

    def test_not_logged_in(self):
        self.client.logout()

        url = reverse("routes:import_activities")
        response = self.client.get(url)
        redirected_response = self.client.get(url, follow=True)

        login_url = "{url}?next={next}".format(url=reverse("login"), next=url)
        error = "Please login to see this page."

        self.assertRedirects(response, login_url)
        self.assertContains(redirected_response, error)

    @responses.activate
    def test_is_activity_supported_manual(self):
        strava_activity = self.load_strava_activity_from_json("manual_activity.json")
        assert not is_activity_supported(strava_activity)

    @responses.activate
    def test_is_activity_supported_unsupported_activity(self):
        strava_activity = self.load_strava_activity_from_json("swim_activity.json")
        assert not is_activity_supported(strava_activity)

    @responses.activate
    def test_is_activity_supported(self):
        strava_activity = self.load_strava_activity_from_json("race_run_activity.json")
        assert is_activity_supported(strava_activity)

    @responses.activate
    def test_save_strava_activity_new_manual_activity(self):
        strava_activity = self.load_strava_activity_from_json("manual_activity.json")
        activity = Activity(athlete=self.athlete, strava_id=strava_activity.id)

        # save the manual strava activity
        activity.update_with_strava_data(strava_activity)

        self.assertEqual(Activity.objects.count(), 1)
        self.assertEqual(
            str(activity),
            "{}: {} - {}".format(
                activity.activity_type, activity.name, activity.athlete
            ),
        )

    @responses.activate
    def test_save_strava_race_run(self):
        strava_activity = self.load_strava_activity_from_json("race_run_activity.json")
        activity = Activity(athlete=self.athlete, strava_id=strava_activity.id)
        activity.update_with_strava_data(strava_activity)
        activity.refresh_from_db()

        self.assertEqual(Activity.objects.count(), 1)
        self.assertEqual(int(activity.workout_type), Activity.RACE_RUN)

        activity_url = "https://www.strava.com/activities/{}".format(activity.strava_id)
        self.assertEqual(activity_url, activity.get_strava_url())
        self.assertAlmostEqual(activity.distance / 1000, activity.get_distance().km)
        self.assertAlmostEqual(
            activity.total_elevation_gain, activity.get_total_elevation_gain().m
        )

    def test_save_strava_activity_add_existing_gear(self):

        # create activity with no gear
        activity = ActivityFactory(gear=None, athlete=self.athlete)

        # create gear
        gear = GearFactory(athlete=self.athlete)

        # fake activity from Strava with a gear_id from an existing gear
        strava_activity = deepcopy(activity)

        # map id back to strava_id
        strava_activity.id = activity.strava_id

        # map total_elevation_gain back to total_elevation_gain and activity_type to type
        strava_activity.total_elevation_gain = activity.total_elevation_gain
        strava_activity.type = activity.activity_type

        # add existing gear to the Strava activity
        strava_activity.gear_id = gear.strava_id

        # update activity with Strava data
        activity.update_with_strava_data(strava_activity)

        self.assertEqual(gear, activity.gear)
        self.assertEqual(Activity.objects.count(), 1)
        self.assertEqual(
            str(gear), "{0} - {1}".format(activity.gear.brand_name, activity.gear.name)
        )

    @responses.activate
    def test_save_strava_activity_add_new_gear(self):

        # create activity with no gear
        activity = ActivityFactory(gear=None, athlete=self.athlete)

        # fake activity from Strava with a new gear_id
        strava_activity = deepcopy(activity)

        # map id back to strava_id
        strava_activity.id = activity.strava_id

        # map total_elevation_gain back to total_elevation_gain and activity_type to type
        strava_activity.total_elevation_gain = activity.total_elevation_gain
        strava_activity.type = activity.activity_type

        # add new gear to the Strava activity
        strava_activity.gear_id = "g123456"

        gear_url = STRAVA_BASE_URL + "/gear/%s" % strava_activity.gear_id
        gear_json = read_data("gear.json", dir_path=CURRENT_DIR)

        # intercept Strava API call to get gear info from Strava
        responses.add(
            responses.GET,
            gear_url,
            content_type="application/json",
            body=gear_json,
            status=200,
        )

        # update the activity with strava data: because of the new gear,
        # it will trigger an update with the Strava API
        activity.update_with_strava_data(strava_activity)

        self.assertEqual(strava_activity.gear_id, activity.gear.strava_id)
        self.assertIsInstance(activity.gear, Gear)
        self.assertEqual(Activity.objects.count(), 1)

    def test_save_strava_activity_remove_gear(self):

        # create activity with gear
        activity = ActivityFactory(athlete=self.athlete)

        # fake a Strava activity as it would be retrieved from the API
        strava_activity = deepcopy(activity)

        # map id back to Strava
        strava_activity.id = activity.strava_id

        # map total_elevation_gain back to total_elevation_gain and activity_type to type
        strava_activity.total_elevation_gain = activity.total_elevation_gain
        strava_activity.type = activity.activity_type

        # remove gear
        strava_activity.gear_id = None

        # save the strava activity
        activity.update_with_strava_data(strava_activity)

        self.assertIsNone(activity.gear)
        self.assertEqual(Activity.objects.count(), 1)

    @responses.activate
    def test_update_strava_activity_deleted(self):

        # create activity
        activity = ActivityFactory(athlete=self.athlete)

        activity_url = ACTIVITY_URL.format(activity.strava_id)
        not_found_json = read_data("activity_not_found.json", dir_path=CURRENT_DIR)

        # API response will be a 404 because it was deleted or
        # the the privacy settings have changed
        responses.add(
            responses.GET,
            activity_url,
            content_type="application/json",
            body=not_found_json,
            status=404,
        )

        # update the activity from strava data
        activity.get_activity_from_strava()

        self.assertEqual(Activity.objects.count(), 0)

    @responses.activate
    def test_update_strava_activity_changed(self):
        strava_activity = self.load_strava_activity_from_json("manual_activity.json")
        activity = Activity(athlete=self.athlete, strava_id=strava_activity.id)
        # save the manual strava activity
        activity.update_with_strava_data(strava_activity)

        self.assertEqual(activity.description, "Manual Description")

        activity_url = ACTIVITY_URL.format(activity.strava_id)
        changed_json = read_data("manual_activity_changed.json", dir_path=CURRENT_DIR)

        responses.replace(
            responses.GET,
            activity_url,
            content_type="application/json",
            body=changed_json,
            status=200,
        )
        strava_activity = activity.get_activity_from_strava()
        activity.update_with_strava_data(strava_activity)

        assert activity.description == ""
        assert Activity.objects.count() == 1

    @responses.activate
    def test_import_strava_activities_task(self):
        # update athlete activities: 2 received
        responses.add(
            responses.GET,
            ACTIVITIES_URL,
            content_type="application/json",
            body=read_data("activities.json", dir_path=CURRENT_DIR),  # two activities
        )
        import_strava_activities_task(self.athlete.id)
        assert Activity.objects.count() == 2

        # update athlete activities: 1 received
        responses.replace(
            responses.GET,
            ACTIVITIES_URL,
            content_type="application/json",
            body=read_data(
                "activities_one.json", dir_path=CURRENT_DIR
            ),  # one activities
        )
        import_strava_activities_task(self.athlete.id)
        assert Activity.objects.count() == 1

        # update athlete activities: 2 received
        responses.replace(
            responses.GET,
            ACTIVITIES_URL,
            content_type="application/json",
            body=read_data("activities.json", dir_path=CURRENT_DIR),  # two activities
        )
        import_strava_activities_task(self.athlete.id)
        assert Activity.objects.count() == 2

        # update activities: 0 received
        responses.replace(
            responses.GET, ACTIVITIES_URL, content_type="application/json", body="[]"
        )
        import_strava_activities_task(self.athlete.id)
        assert Activity.objects.count() == 0

    @responses.activate
    def test_are_streams_valid_missing_streams(self):
        activity = ActivityFactory(athlete=self.athlete)

        responses.add(
            responses.GET,
            STREAMS_URL.format(activity.strava_id),
            content_type="application/json",
            body=read_data("missing_streams.json", dir_path=CURRENT_DIR),
            status=200,
        )
        strava_streams = activity.get_streams_from_strava()

        assert not are_streams_valid(strava_streams)

    @responses.activate
    def test_are_streams_valid_missing_values(self):
        activity = ActivityFactory(athlete=self.athlete)

        responses.add(
            responses.GET,
            STREAMS_URL.format(activity.strava_id),
            content_type="application/json",
            body=read_data("missing_values.json", dir_path=CURRENT_DIR),
            status=200,
        )
        strava_streams = activity.get_streams_from_strava()

        assert not are_streams_valid(strava_streams)

    @responses.activate
    def test_get_streams_from_strava_all_streams(self):
        activity = ActivityFactory(athlete=self.athlete)
        responses.add(
            responses.GET,
            STREAMS_URL.format(activity.strava_id),
            content_type="application/json",
            body=read_data("streams.json", dir_path=CURRENT_DIR),
            status=200,
            match_querystring=False,
        )
        strava_streams = activity.get_streams_from_strava()
        assert len(strava_streams) == 4
        assert all(
            stream_type in activity.streams.columns for stream_type in STREAM_TYPES
        )

    @responses.activate
    def test_update_activity_streams_from_strava(self):
        activity = ActivityFactory(athlete=self.athlete, streams=None)

        responses.add(
            responses.GET,
            STREAMS_URL.format(activity.strava_id),
            content_type="application/json",
            body=read_data("streams.json", dir_path=CURRENT_DIR),
            status=200,
            match_querystring=False,
        )

        activity.update_activity_streams_from_strava()

        field = DataFrameField()
        full_path = field.storage.path(activity.streams.filepath)

        assert isinstance(activity.streams, DataFrame)
        assert all(
            stream_type in activity.streams.columns for stream_type in STREAM_TYPES
        )
        assert str(self.athlete.id) in full_path

    @responses.activate
    def test_update_activity_streams_from_strava_missing_streams(self):
        activity = ActivityFactory(athlete=self.athlete, streams=None)

        responses.add(
            responses.GET,
            STREAMS_URL.format(activity.strava_id),
            content_type="application/json",
            body=read_data("missing_streams.json", dir_path=CURRENT_DIR),
            status=200,
            match_querystring=False,
        )
        activity.update_activity_streams_from_strava()

        assert activity.streams is None
        assert activity.skip_streams_import

    @override_settings(
        STRAVA_VERIFY_TOKEN="RIGHT_TOKEN",
    )
    def test_strava_webhook_callback_url_token(self):
        # subscription validation successful
        webhook_url = reverse("routes:strava_webhook")
        data = {
            "hub.verify_token": "RIGHT_TOKEN",
            "hub.challenge": "challenge",
            "hub.mode": "subscribe",
        }
        response = self.client.get(webhook_url, data)
        self.assertContains(response, data["hub.challenge"])

        # subscription validation with wrong token
        data["hub.verify_token"] = "WRONG_TOKEN"

        response = self.client.get(webhook_url, data)
        self.assertEqual(response.status_code, 401)

    @responses.activate
    @override_settings(
        celery_task_always_eager=True,
        celery_task_eager_propagates=True,
    )
    def test_strava_webhook_callback_event(self):
        webhook_url = reverse("routes:strava_webhook")
        activity_response = read_data("race_run_activity.json", dir_path=CURRENT_DIR)
        event_data = json.loads(read_data("event.json", dir_path=CURRENT_DIR))

        # intercept call triggered by the event to Strava API
        responses.add(
            responses.GET,
            ACTIVITY_URL.format(event_data["object_id"]),
            body=activity_response,
            status=200,
        )

        # event posted by Strava
        response = self.client.post(webhook_url, event_data, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(WebhookTransaction.objects.count(), 1)

        transaction = WebhookTransaction.objects.first()
        self.assertEqual(
            str(transaction),
            "{0} - {1}".format(
                transaction.get_status_display(),
                transaction.date_generated,
            ),
        )

    def test_import_strava_activities_view(self):
        import_url = reverse("routes:import_activities")

        with patch(
            "homebytwo.routes.tasks.import_strava_activities_task.delay"
        ) as mock_task:
            response = self.client.get(import_url)
            self.assertRedirects(response, reverse("routes:activities"))
            self.assertTrue(mock_task.called)

    def test_import_strava_activity_streams(self):
        import_url = reverse("routes:import_streams")
        activity_type = ActivityTypeFactory.create(name="Run")
        ActivityFactory.create_batch(
            5, athlete=self.athlete, activity_type=activity_type, streams=None
        )

        with patch(
            "homebytwo.routes.tasks.import_strava_activity_streams_task.delay"
        ) as mock_task:
            response = self.client.get(import_url)
            self.assertRedirects(response, reverse("routes:activities"))
            assert mock_task.called

    def test_train_prediction_models(self):
        train_url = reverse("routes:train_models")
        activity_type = ActivityTypeFactory.create(name="Run")
        ActivityFactory.create_batch(
            5,
            athlete=self.athlete,
            activity_type=activity_type,
        )

        with patch(
            "homebytwo.routes.tasks.train_prediction_models_task.delay"
        ) as mock_task:
            response = self.client.get(train_url)
            self.assertRedirects(response, reverse("routes:activities"))
            self.assertTrue(mock_task.called)

    def test_view_activity_list_empty(self):
        activity_list_url = reverse("routes:activities")
        response = self.client.get(activity_list_url)
        self.assertEqual(response.status_code, 200)
