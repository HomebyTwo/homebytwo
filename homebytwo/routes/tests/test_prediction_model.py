from ..prediction_model import PredictionModel
from .factories import RouteFactory


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
    assert prediction_model.categories == "auto"
    assert prediction_model.pipeline.named_steps["columntransformer"]
    assert prediction_model.pipeline.named_steps["ridge"]


def test_prediction_model_with_custom_parameters():
    prediction_model = PredictionModel(
        categorical_columns=["gear", "workout_type"],
        numerical_columns=[],
        polynomial_columns=[],
    )

    assert prediction_model.categories == "auto"
    assert prediction_model.numerical_columns == []


def test_track_return_prediction_model(test_athlete):
    route = RouteFactory()
    route.calculate_projected_time_schedule(test_athlete.user)

    assert "schedule" in route.data.columns
    assert "pace" in route.data.columns
