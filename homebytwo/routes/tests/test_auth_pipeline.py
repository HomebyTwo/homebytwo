from homebytwo.routes import auth_pipeline
from .factories import ActivityFactory


def test_auth_pipeline_new_athlete(athlete, celery, mocker):
    mock_import_task = mocker.patch(
        "homebytwo.routes.tasks.import_strava_activities_task.run"
    )
    mock_streams_task = mocker.patch(
        "homebytwo.routes.tasks.import_strava_activities_streams_task.run"
    )
    mock_train_task = mocker.patch(
        "homebytwo.routes.tasks.train_prediction_models_task.run"
    )

    auth_pipeline.import_strava(user=athlete.user, is_new=True)
    mock_import_task.assert_called_with(athlete_id=athlete.id)
    mock_streams_task.assert_called
    mock_train_task.assert_called_with(athlete_id=athlete.id)


def test_auth_pipeline_existing_athlete(athlete, celery, mocker):
    ActivityFactory.create_batch(5, athlete=athlete, streams=None)
    ActivityFactory.create_batch(5, athlete=athlete)

    activities = athlete.activities.filter(streams__isnull=True)
    activity_ids = list(activities.values_list("strava_id", flat=True))
    assert athlete.activities.count() == 10

    mock_streams_task = mocker.patch(
        "homebytwo.routes.tasks.import_strava_activities_streams_task.run"
    )
    mock_train_task = mocker.patch(
        "homebytwo.routes.tasks.train_prediction_models_task.run"
    )
    auth_pipeline.import_strava(user=athlete.user, is_new=False)
    mock_streams_task.assert_called_with(activity_ids)
    mock_train_task.assert_called_with(athlete_id=athlete.id)
