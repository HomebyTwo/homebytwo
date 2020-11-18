from django.urls import reverse

from ..forms import ActivityPerformanceForm
from ..models import ActivityType
from ..prediction_model import PredictionModel
from .factories import (
    ActivityFactory,
    ActivityPerformanceFactory,
    ActivityTypeFactory,
    GearFactory,
    RouteFactory,
)


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
    assert prediction_model.onehot_encoder_categories == "auto"
    assert prediction_model.pipeline.named_steps["columntransformer"]
    assert prediction_model.pipeline.named_steps["linearregression"]


def test_prediction_model_with_custom_parameters():
    prediction_model = PredictionModel(
        categorical_columns=["gear", "workout_type"],
        numerical_columns=[],
    )

    assert prediction_model.onehot_encoder_categories == "auto"
    assert prediction_model.numerical_columns == []


def test_train_prediction_model_data_no_data(athlete):
    activity_performance = ActivityPerformanceFactory(athlete=athlete)
    activity_type = activity_performance.activity_type.name
    result = activity_performance.train_prediction_model()
    assert f"No training data found for activity type: {activity_type}" in result


def test_train_prediction_model_data_success(athlete):
    activity_performance = ActivityPerformanceFactory(athlete=athlete)
    activity = ActivityFactory(
        athlete=athlete, activity_type=activity_performance.activity_type
    )
    result = activity_performance.train_prediction_model()

    assert "Model successfully trained" in result
    assert activity_performance.gear_categories == [activity.gear.strava_id]
    assert activity_performance.workout_type_categories == [
        activity.get_workout_type_display()
    ]


def test_train_prediction_model_data_default_run(athlete):
    activity_performance = ActivityPerformanceFactory(athlete=athlete)
    activity = ActivityFactory(
        athlete=athlete,
        activity_type=activity_performance.activity_type,
        workout_type=0,
    )
    result = activity_performance.train_prediction_model()

    assert "Model successfully trained" in result
    assert activity_performance.gear_categories == [activity.gear.strava_id]
    assert activity_performance.workout_type_categories == [
        activity.get_workout_type_display()
    ]


def test_train_prediction_model_data_success_no_gear_no_workout_type(athlete):
    activity_performance = ActivityPerformanceFactory(athlete=athlete)
    ActivityFactory(
        athlete=athlete,
        activity_type=activity_performance.activity_type,
        gear=None,
        workout_type=None,
    )
    result = activity_performance.train_prediction_model()
    assert "Model successfully trained" in result
    assert activity_performance.gear_categories == ["None"]
    assert activity_performance.workout_type_categories == ["None"]


def test_get_activity_performance_training_data(athlete):
    activity_performance = ActivityPerformanceFactory(athlete=athlete)
    ActivityFactory(athlete=athlete, activity_type=activity_performance.activity_type)
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


def test_get_activity_training_data(athlete):
    activity_performance = ActivityPerformanceFactory(athlete=athlete)
    activity = ActivityFactory(
        athlete=athlete, activity_type=activity_performance.activity_type
    )
    activity_data = activity.get_training_data()
    assert activity_data.shape == (99, 15)


def test_track_return_prediction_model(athlete):
    route = RouteFactory()
    route.calculate_projected_time_schedule(athlete.user)

    assert "schedule" in route.data.columns
    assert "pace" in route.data.columns


def test_activity_performance_form_no_choices(athlete):
    activity_performance = ActivityPerformanceFactory(athlete=athlete)
    form = ActivityPerformanceForm(
        route=RouteFactory(activity_type=activity_performance.activity_type),
        athlete=athlete,
    )

    assert "gear" not in form.fields
    assert "workout_type" not in form.fields


def test_activity_performance_form(athlete):
    gears = GearFactory.create_batch(5)
    gear_categories = [gear.strava_id for gear in gears] + ["None"]
    activity_performance = ActivityPerformanceFactory(
        athlete=athlete,
        gear_categories=gear_categories,
        workout_type_categories=["None", "long run"],
    )

    form = ActivityPerformanceForm(
        route=RouteFactory(activity_type=activity_performance.activity_type),
        athlete=athlete,
    )

    assert len(form.fields["gear"].choices) == 6
    assert form.fields["workout_type"].choices == [
        ("None", "None"),
        ("long run", "long run"),
    ]


def test_activity_performance_form_no_activity_performance(athlete):
    athlete_activity_type, other_activity_type = ActivityTypeFactory.create_batch(2)
    route = RouteFactory(activity_type=other_activity_type)
    ActivityPerformanceFactory(
        athlete=athlete,
        activity_type=athlete_activity_type,
    )
    form = ActivityPerformanceForm(route=route, athlete=athlete)

    assert len(form.fields["activity_type"].choices) == len(
        ActivityType.SUPPORTED_ACTIVITY_TYPES
    )
    assert "gear" not in form.fields
    assert "workout_type" not in form.fields


def test_activity_performance_form_not_logged_in(athlete):
    form = ActivityPerformanceForm(route=RouteFactory(), athlete=None)

    assert len(form.fields["activity_type"].choices) == len(
        ActivityType.SUPPORTED_ACTIVITY_TYPES
    )
    assert "gear" not in form.fields
    assert "workout_type" not in form.fields


def test_activity_performance_form_invalid_post_data(athlete):
    route = RouteFactory()
    original_route_activity_type = route.activity_type
    invalid_activity_type_name = "foobar"
    ActivityPerformanceForm(
        route=route,
        athlete=athlete,
        data={"activity_type": invalid_activity_type_name},
    )

    assert route.activity_type == original_route_activity_type


def test_activity_performance_form_change_activity_type(athlete):
    one_activity_type, other_activity_type = ActivityTypeFactory.create_batch(2)
    route = RouteFactory(activity_type=one_activity_type)
    ActivityPerformanceForm(
        route=route,
        athlete=athlete,
        data={"activity_type": other_activity_type.name},
    )

    assert route.activity_type == other_activity_type


def test_performance_form_on_route_page(athlete, client):
    (
        activity_performance,
        other_activity_performance,
        *_,
    ) = ActivityPerformanceFactory.create_batch(8, athlete=athlete)
    route = RouteFactory(activity_type=activity_performance.activity_type)
    url = reverse("routes:route", kwargs={"pk": route.pk})
    selected_activity_type = other_activity_performance.activity_type
    data = {"activity_type": selected_activity_type}
    response = client.post(url, data=data)

    athlete_activity_types = athlete.performances.all()

    selected = '<option value="{}" selected>{}</option>'.format(
        selected_activity_type.name, selected_activity_type.get_name_display()
    )

    assert str(activity_performance) == "{} - {} - {:.2%}".format(
        athlete.user.username,
        activity_performance.activity_type.name,
        activity_performance.model_score,
    )
    assert response.status_code == 200
    assert selected in response.content.decode("utf-8")
    assert all(
        [
            activity_type in response.content.decode("utf-8")
            for activity_type in athlete_activity_types.values_list(
                "activity_type__name", flat=True
            )
        ]
    )
