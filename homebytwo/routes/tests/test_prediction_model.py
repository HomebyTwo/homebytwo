from ..prediction_model import PredictionModel
from .factories import ActivityFactory, ActivityPerformanceFactory, RouteFactory


def test_prediction_model_with_defaults():
    prediction_model = PredictionModel()

    assert prediction_model.numerical_columns == [
        "gradient",
        "total_elevation_gain",
        "total_distance",
    ]

    assert prediction_model.categorical_columns == ["gear", "workout_type"]
    assert prediction_model.numerical_columns == [
        "gradient",
        "total_elevation_gain",
        "total_distance",
    ]
    assert prediction_model.polynomial_columns == ["gradient"]
    assert prediction_model.onehot_encoder_categories is None
    assert prediction_model.pipeline.named_steps["columntransformer"]
    assert prediction_model.pipeline.named_steps["ridge"]


def test_prediction_model_with_custom_parameters():
    prediction_model = PredictionModel(
        categorical_columns=["gear", "workout_type"], numerical_columns=[],
    )

    assert prediction_model.onehot_encoder_categories is None
    assert prediction_model.numerical_columns == []


def test_train_prediction_model_data_no_data(test_athlete):
    activity_performance = ActivityPerformanceFactory(athlete=test_athlete)
    activity_type = activity_performance.activity_type.name
    result = activity_performance.train_prediction_model()
    assert f"No training data found for activity type: {activity_type}" in result


def test_train_prediction_model_data_success(test_athlete):
    activity_performance = ActivityPerformanceFactory(athlete=test_athlete)
    activity = ActivityFactory(
        athlete=test_athlete, activity_type=activity_performance.activity_type
    )
    result = activity_performance.train_prediction_model()
    assert "Model successfully trained" in result
    assert activity_performance.onehot_encoder_categories == [
        [activity.gear.strava_id],
        [str(activity.workout_type)],
    ]


def test_train_prediction_model_data_success_no_gear_no_workout_type(test_athlete):
    activity_performance = ActivityPerformanceFactory(athlete=test_athlete)
    ActivityFactory(
        athlete=test_athlete,
        activity_type=activity_performance.activity_type,
        gear=None,
        workout_type=None,
    )
    result = activity_performance.train_prediction_model()
    assert "Model successfully trained" in result
    assert activity_performance.onehot_encoder_categories == [["None"], ["None"]]


def test_get_activity_performance_training_data(test_athlete):
    activity_performance = ActivityPerformanceFactory(athlete=test_athlete)
    ActivityFactory(
        athlete=test_athlete, activity_type=activity_performance.activity_type
    )
    observations = activity_performance.get_training_data()

    assert all(
        column in observations.columns
        for column in [
            "gear",
            "workout_type",
            "gradient",
            "pace",
            "total_distance",
            "total_elevation_gain",
        ]
    )


def test_get_activity_training_data(test_athlete):
    activity_performance = ActivityPerformanceFactory(athlete=test_athlete)
    activity = ActivityFactory(
        athlete=test_athlete, activity_type=activity_performance.activity_type
    )
    activity_data = activity.get_training_data()
    assert activity_data.shape == (99, 17)


def test_track_return_prediction_model(test_athlete):
    route = RouteFactory()
    route.calculate_projected_time_schedule(test_athlete.user)

    assert "schedule" in route.data.columns
    assert "pace" in route.data.columns
