from pandas import DataFrame
from sklearn.compose import make_column_transformer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, PolynomialFeatures


class PredictionModel:
    """
    the sklearn pipeline for preprocessing data and
    applying a linear regression model to predict the athlete's pace.

    this class is used both for training the model and using the model for predictions.

    to use the pipeline for training, no parameter is required when initializing the model instance.
    to restore the model for predictions, pass the regression and preproccessing parameters found in training.
    """

    def __init__(
        self,
        numerical_columns=None,
        categorical_columns=None,
        polynomial_columns=None,
        regression_intercept=None,
        regression_coefficients=None,
        onehot_encoder_categories=None,
    ):
        # set column defaults
        if not numerical_columns:
            self.numerical_columns = [
                "gradient",
                "total_elevation_gain",
                "total_distance",
            ]
        else:
            self.numerical_columns = numerical_columns

        if not categorical_columns:
            self.categorical_columns = ["gear", "workout_type"]
        else:
            self.categorical_columns = numerical_columns

        if not polynomial_columns:
            self.polynomial_columns = ["gradient"]
        else:
            self.polynomial_columns = polynomial_columns

        # restore categories of the one-hot encoder if provided
        categories = onehot_encoder_categories if onehot_encoder_categories else "auto"

        # use these categories for creating the preprocessor
        self.preprocessor = make_column_transformer(
            (OneHotEncoder(categories=categories), self.categorical_columns),
            (PolynomialFeatures(2), self.polynomial_columns),
            remainder="passthrough",
        )

        # to use the pipeline for predictions,
        # we must fit the preprocessor with dummy data first
        if onehot_encoder_categories:
            # any numerical value will do
            dummy_numerical_data = [1.0 for column in self.numerical_columns]
            # category must be recognised by the one-hot encoder
            dummy_categorical_data = [
                category_list[0] for category_list in onehot_encoder_categories
            ]

            # create a DataFrame with one row
            dummy_row = DataFrame(
                data=[dummy_numerical_data + dummy_categorical_data],
                columns=self.numerical_columns + self.categorical_columns,
            )

            # fit the preprocessor on dummy data
            self.preprocessor.fit(dummy_row)

        # join preprocessor and linear model into a pipeline
        self.pipeline = make_pipeline(self.preprocessor, Ridge(),)

        # restore trained model if regression parameters are provided
        if regression_intercept and regression_coefficients is not None:
            regression = self.pipeline.named_steps["ridge"]
            regression.coef_ = regression_coefficients
            regression.intercept_ = regression_intercept
