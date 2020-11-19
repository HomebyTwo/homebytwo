from numpy import array
from pandas import DataFrame
from sklearn.compose import make_column_transformer
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import cross_val_score, train_test_split
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
        if numerical_columns is None:
            self.numerical_columns = [
                "gradient",
                "total_elevation_gain",
                "total_distance",
            ]
        else:
            self.numerical_columns = numerical_columns

        if categorical_columns is None:
            self.categorical_columns = ["gear", "workout_type"]
        else:
            self.categorical_columns = categorical_columns

        if polynomial_columns is None:
            self.polynomial_columns = ["gradient"]
        else:
            self.polynomial_columns = polynomial_columns

        # restore categories of the one-hot encoder if provided
        if onehot_encoder_categories:
            self.onehot_encoder_categories = onehot_encoder_categories
        else:
            self.onehot_encoder_categories = "auto"

        # use these categories for creating the preprocessor
        self.preprocessor = make_column_transformer(
            (
                OneHotEncoder(
                    handle_unknown="ignore", categories=self.onehot_encoder_categories
                ),
                self.categorical_columns,
            ),
            (PolynomialFeatures(2), self.polynomial_columns),
            remainder="passthrough",
        )
        self.model_score = 0.0
        self.cv_scores = array([0] * 5)

        # to use the pipeline for predictions,
        # we must fit the preprocessor with dummy data first
        if onehot_encoder_categories:
            # any numerical value will do
            dummy_numerical_data = [1.0] * len(self.numerical_columns)
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
        self.pipeline = make_pipeline(
            self.preprocessor,
            LinearRegression(),
        )

        # restore trained model if regression parameters are provided
        if regression_intercept and regression_coefficients is not None:
            regression = self.pipeline.named_steps["linearregression"]
            regression.coef_ = regression_coefficients
            regression.intercept_ = regression_intercept

    def train(self, y, x, test_size=0.3):
        """
        train the prediction model
        """
        # split data into training and testing data
        x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=test_size)

        # fit model with training data
        self.pipeline.fit(x_train, y_train)

        # evaluate model with test data
        self.model_score = self.pipeline.score(x_test, y_test)
        self.cv_scores = cross_val_score(self.pipeline, x_test, y_test, cv=5)

        # update onehot_encoder_categories attribute
        if self.categorical_columns:
            self.onehot_encoder_categories = (
                self.pipeline.named_steps["columntransformer"]
                .named_transformers_["onehotencoder"]
                .categories_
            )
