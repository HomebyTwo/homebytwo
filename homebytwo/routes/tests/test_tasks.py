from datetime import timedelta

from homebytwo.conftest import STRAVA_API_BASE_URL
from homebytwo.routes.models import WebhookTransaction
from homebytwo.routes.tasks import (
    import_strava_activities_streams_task,
    import_strava_activities_task,
    import_strava_activity_streams_task,
    process_strava_events,
    train_prediction_models_task,
)
from homebytwo.routes.tests.factories import (
    ActivityFactory,
    ActivityTypeFactory,
    WebhookTransactionFactory,
)

STRAVA_STREAMS_URL = (
    STRAVA_API_BASE_URL + "activities/{}/streams/time,altitude,distance,moving"
)
GARMIN_UPLOAD_URL = "https://connect.garmin.com/modern/proxy/upload-service/upload/gpx"


def test_import_strava_activities_task(athlete, mock_call_json_response):
    url = STRAVA_API_BASE_URL + "athlete/activities"
    call = import_strava_activities_task
    response_json = "activities.json"

    mock_call_json_response(call, url, response_json, athlete_id=athlete.id)

    assert athlete.activities.count() == 2
    assert athlete.activities_imported


def test_import_strava_activities_task_server_error(athlete, mock_call_server_error):
    url = STRAVA_API_BASE_URL + "athlete/activities"
    call = import_strava_activities_task
    response_json = "activities.json"
    response = mock_call_server_error(call, url, response_json, athlete_id=athlete.id)
    assert response == []


def test_import_strava_activities_streams_task(athlete, mocker):
    activities = ActivityFactory.create_batch(10, athlete=athlete, streams=None)
    activity_ids = [activity.strava_id for activity in activities]

    mock_task = mocker.patch(
        "homebytwo.routes.tasks.import_strava_activity_streams_task.run"
    )
    import_strava_activities_streams_task(activity_ids)
    mock_task.assert_called


def test_import_strava_activity_streams_task_success(athlete, mock_call_json_response):
    activity = ActivityFactory(athlete=athlete, streams=None)
    url = STRAVA_STREAMS_URL.format(activity.strava_id)
    expected = "Streams successfully imported for activity {}".format(
        activity.strava_id
    )
    response = mock_call_json_response(
        import_strava_activity_streams_task,
        url,
        "streams.json",
        strava_id=activity.strava_id,
    )
    activity.refresh_from_db()
    assert activity.streams is not None
    assert expected in response


def test_update_activity_streams_from_strava_skip(athlete):
    activity = ActivityFactory(athlete=athlete, streams=None, skip_streams_import=True)
    expected = "Skipped importing streams for activity {}. ".format(activity.strava_id)
    response = import_strava_activity_streams_task(activity.strava_id)
    assert activity.streams is None
    assert expected in response


def test_import_strava_activity_streams_task_missing(athlete, mock_call_json_response):
    activity = ActivityFactory(athlete=athlete, streams=None)
    url = STRAVA_STREAMS_URL.format(str(activity.strava_id))

    expected = "Streams not imported for activity {}".format(activity.strava_id)
    response = mock_call_json_response(
        import_strava_activity_streams_task,
        url,
        "missing_streams.json",
        strava_id=activity.strava_id,
    )
    activity.refresh_from_db()
    assert activity.streams is None
    assert expected in response


def test_import_strava_activity_streams_task_deleted(athlete):
    non_existent_id = 9_999_999_999_999
    expected = "Activity {} has been deleted from the Database".format(non_existent_id)
    response = import_strava_activity_streams_task(non_existent_id)
    assert expected in response


def test_import_strava_activity_streams_task_connection_error(
    athlete, mock_call_connection_error
):
    activity = ActivityFactory(athlete=athlete, streams=None)
    call = import_strava_activity_streams_task
    url = STRAVA_STREAMS_URL.format(activity.strava_id)

    response = mock_call_connection_error(call, url, strava_id=activity.strava_id)
    expected = "Streams for activity {} could not be retrieved from Strava".format(
        activity.strava_id
    )

    assert expected in response


def test_import_strava_activity_streams_task_server_error(
    athlete, mock_call_server_error
):
    activity = ActivityFactory(athlete=athlete, streams=None)
    call = import_strava_activity_streams_task
    url = STRAVA_STREAMS_URL.format(activity.strava_id)

    response = mock_call_server_error(
        call, url, "streams.json", strava_id=activity.strava_id
    )
    expected = "Streams for activity {} could not be retrieved from Strava".format(
        activity.strava_id
    )

    assert expected in response


def test_train_prediction_models_task(athlete):
    ActivityFactory.create_batch(
        3, athlete=athlete, activity_type=ActivityTypeFactory(name="Run")
    )
    ActivityFactory.create_batch(
        2, athlete=athlete, activity_type=ActivityTypeFactory(name="Hike")
    )
    ActivityFactory.create_batch(
        1, athlete=athlete, activity_type=ActivityTypeFactory(name="Ride")
    )

    response = train_prediction_models_task(athlete.id)
    expected = f"Prediction models trained for athlete: {athlete}."
    assert expected in response

    athlete_prediction_models = athlete.performances
    assert athlete_prediction_models.count() == 3
    for model in athlete_prediction_models.all():
        assert not model.model_score == 0.0


def test_train_prediction_models_task_no_activity(athlete):
    response = train_prediction_models_task(athlete.id)
    expected = f"No prediction model trained for athlete: {athlete}"
    assert expected in response


def test_process_strava_events_create_update_delete(athlete, mock_call_json_response):
    activity_strava_id = 1234567890
    WebhookTransactionFactory(
        action="create",
        athlete_strava_id=athlete.strava_id,
        activity_strava_id=activity_strava_id,
    )
    call = process_strava_events
    url = STRAVA_API_BASE_URL + "activities/" + str(activity_strava_id)
    response_json = "race_run_activity.json"
    mock_call_json_response(call, url, response_json)

    transactions = WebhookTransaction.objects.all()
    processed_transactions = transactions.filter(status=WebhookTransaction.PROCESSED)

    assert transactions.count() == 1
    assert processed_transactions.count() == 1
    assert athlete.activities.count() == 1

    WebhookTransactionFactory(
        action="update",
        athlete_strava_id=athlete.strava_id,
        activity_strava_id=activity_strava_id,
    )
    process_strava_events()
    assert processed_transactions.count() == 2
    assert athlete.activities.count() == 1

    WebhookTransactionFactory(
        action="delete",
        athlete_strava_id=athlete.strava_id,
        activity_strava_id=activity_strava_id,
    )
    process_strava_events()
    assert processed_transactions.count() == 3
    assert athlete.activities.count() == 0


def test_process_strava_events_duplicates(athlete):

    first_transaction = WebhookTransactionFactory(
        action="create", athlete_strava_id=athlete.strava_id
    )
    WebhookTransactionFactory(
        action="delete",
        athlete_strava_id=athlete.strava_id,
        date_generated=first_transaction.date_generated + timedelta(minutes=2),
    )
    process_strava_events()

    transactions = WebhookTransaction.objects.all()
    processed_transactions = transactions.filter(status=WebhookTransaction.PROCESSED)
    skipped_transactions = transactions.filter(status=WebhookTransaction.SKIPPED)
    assert processed_transactions.count() == 1
    assert processed_transactions.first().body["aspect_type"] == "delete"
    assert skipped_transactions.count() == 1


def test_process_events_deleted_activity(athlete, mock_call_not_found):
    activity = ActivityFactory()
    WebhookTransactionFactory(
        athlete_strava_id=athlete.strava_id, activity_strava_id=activity.strava_id
    )
    call = process_strava_events
    url = STRAVA_API_BASE_URL + "activities/" + str(activity.strava_id)
    mock_call_not_found(call, url)


def test_process_strava_events_errors(athlete, mock_call_connection_error):
    WebhookTransactionFactory(athlete_strava_id=0)
    WebhookTransactionFactory(athlete_strava_id=athlete.strava_id, activity_strava_id=0)
    WebhookTransactionFactory(
        athlete_strava_id=athlete.strava_id, object_type="athlete"
    )
    call = process_strava_events
    url = STRAVA_API_BASE_URL + "activities/0"
    mock_call_connection_error(call, url)

    transactions = WebhookTransaction.objects.all()
    assert transactions.filter(status=WebhookTransaction.ERROR).count() == 2
    assert transactions.filter(status=WebhookTransaction.PROCESSED).count() == 1
