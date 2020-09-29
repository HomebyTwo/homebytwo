from datetime import timedelta
from homebytwo.routes.models import WebhookTransaction
from homebytwo.routes.tasks import (
    import_strava_activities_task,
    import_strava_activities_streams_task,
    import_strava_activity_streams_task,
    train_prediction_models_task,
    process_strava_events,
)
from homebytwo.routes.tests.factories import (
    ActivityFactory,
    ActivityTypeFactory,
    WebhookTransactionFactory,
)

STRAVA_API_BASE_URL = "https://www.strava.com/api/v3/"
STRAVA_STREAMS_URL = (
    STRAVA_API_BASE_URL + "activities/{}/streams/time,altitude,distance,moving"
)
GARMIN_UPLOAD_URL = "https://connect.garmin.com/modern/proxy/upload-service/upload/gpx"


def test_import_strava_activities_task(athlete, intercept):
    url = STRAVA_API_BASE_URL + "athlete/activities"
    call = import_strava_activities_task
    response_json = "activities.json"

    intercept(call, url, response_json, athlete_id=athlete.id)

    assert athlete.activities.count() == 2


def test_import_strava_activities_streams_task(athlete, mocker):
    activities = ActivityFactory.create_batch(10, athlete=athlete, streams=None)
    activity_ids = [activity.strava_id for activity in activities]

    mock_task = mocker.patch(
        "homebytwo.routes.tasks.import_strava_activity_streams_task.run"
    )
    import_strava_activities_streams_task(activity_ids)
    mock_task.assert_called


def test_import_strava_activity_streams_task_success(athlete, intercept):
    activity = ActivityFactory(athlete=athlete, streams=None)
    url = STRAVA_STREAMS_URL.format(str(activity.strava_id))
    expected = "Streams successfully imported for activity {}".format(
        activity.strava_id
    )
    response = intercept(
        import_strava_activity_streams_task,
        url,
        "streams.json",
        strava_id=activity.strava_id,
    )
    activity.refresh_from_db()
    assert activity.streams is not None
    assert expected in response


def test_import_strava_activity_streams_task_missing(athlete, intercept):
    activity = ActivityFactory(athlete=athlete, streams=None)
    url = STRAVA_STREAMS_URL.format(str(activity.strava_id))

    expected = "Streams not imported for activity {}".format(activity.strava_id)
    response = intercept(
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
    athlete, connection_error
):
    activity = ActivityFactory(athlete=athlete, streams=None)
    call = import_strava_activity_streams_task
    url = STRAVA_STREAMS_URL.format(activity.strava_id)

    response = connection_error(call, url, strava_id=activity.strava_id)
    expected = "Streams for activity {} could not be retrieved from Strava".format(
        activity.strava_id
    )

    assert expected in response


def test_import_strava_activity_streams_task_server_error(athlete, server_error):
    activity = ActivityFactory(athlete=athlete, streams=None)
    call = import_strava_activity_streams_task
    url = STRAVA_STREAMS_URL.format(activity.strava_id)

    response = server_error(call, url, "streams.json", strava_id=activity.strava_id)
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

    athlete_prediction_models = athlete.activityperformance_set
    assert athlete_prediction_models.count() == 3
    for model in athlete_prediction_models.all():
        assert not model.model_score == 0.0


def test_train_prediction_models_task_no_activity(athlete):
    response = train_prediction_models_task(athlete.id)
    expected = f"No prediction model trained for athlete: {athlete}"
    assert expected in response


def test_process_strava_events_create_update_delete(athlete, intercept):
    activity_strava_id = 1234567890
    WebhookTransactionFactory(
        action="create",
        athlete_strava_id=athlete.strava_id,
        activity_strava_id=activity_strava_id,
    )
    call = process_strava_events
    url = STRAVA_API_BASE_URL + "activities/" + str(activity_strava_id)
    response_json = "manual_activity.json"
    intercept(call, url, response_json)

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
    intercept(call, url, response_json)
    assert processed_transactions.count() == 2
    assert athlete.activities.count() == 1

    WebhookTransactionFactory(
        action="delete",
        athlete_strava_id=athlete.strava_id,
        activity_strava_id=activity_strava_id,
    )
    call()
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


def test_process_strava_events_errors(athlete, connection_error):
    WebhookTransactionFactory(athlete_strava_id=0)
    WebhookTransactionFactory(athlete_strava_id=athlete.strava_id, activity_strava_id=0)
    WebhookTransactionFactory(
        athlete_strava_id=athlete.strava_id, object_type="athlete"
    )

    # process the event
    call = process_strava_events
    url = STRAVA_API_BASE_URL + "activities/0"
    connection_error(call, url)

    transactions = WebhookTransaction.objects.all()
    assert transactions.filter(status=WebhookTransaction.ERROR).count() == 2
    assert transactions.filter(status=WebhookTransaction.PROCESSED).count() == 1
