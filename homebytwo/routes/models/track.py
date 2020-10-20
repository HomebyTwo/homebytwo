import logging
from datetime import timedelta
from uuid import uuid4

from django.contrib.gis.db import models
from django.contrib.gis.geos import LineString
from django.contrib.gis.measure import D

from easy_thumbnails.fields import ThumbnailerImageField
from numpy import interp

from ...core.models import TimeStampedModel
from ..fields import DataFrameField
from ..prediction_model import PredictionModel
from ..utils import get_image_path, get_places_within
from . import ActivityPerformance, ActivityType, Place

logger = logging.getLogger(__name__)


def athlete_data_directory_path(instance, filename):
    # streams will upload to MEDIA_ROOT/athlete_<id>/<filename>
    return f"athlete_{instance.athlete.id}/data/{filename}"


class Track(TimeStampedModel):
    class Meta:
        abstract = True

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    image = ThumbnailerImageField(upload_to=get_image_path, blank=True, null=True)

    # Main activity of the track: default=hike
    activity_type = models.ForeignKey(
        ActivityType, default=1, on_delete=models.SET_DEFAULT
    )

    # link to athlete
    athlete = models.ForeignKey(
        "Athlete", on_delete=models.CASCADE, related_name="tracks"
    )

    # elevation gain in m
    total_elevation_gain = models.FloatField("Total elevation gain in m", default=0)

    # elevation loss in m
    total_elevation_loss = models.FloatField("Total elevation loss in m", default=0)

    # route distance in m
    total_distance = models.FloatField("Total length of the track in m", default=0)

    # geographic information
    geom = models.LineStringField("line geometry", srid=21781)

    # Start and End-place
    start_place = models.ForeignKey(
        Place, null=True, related_name="starts_%(class)s", on_delete=models.SET_NULL
    )

    end_place = models.ForeignKey(
        Place, null=True, related_name="ends_%(class)s", on_delete=models.SET_NULL
    )

    # uuid field to generate unique file names
    uuid = models.UUIDField(default=uuid4, editable=False)

    # track data as a pandas DataFrame
    data = DataFrameField(
        null=True, upload_to=athlete_data_directory_path, unique_fields=["uuid"]
    )

    def calculate_step_distances(self, min_distance: float, commit=True):
        """
        calculate distance between each row, removing steps where distance is too small.
        """
        data = self.data.copy()
        data["geom"], srid = self.geom, self.geom.srid

        data.drop(data[data.distance.diff() < min_distance].index, inplace=True)
        data["step_distance"] = data.distance.diff()

        try:
            self.geom = LineString(data.geom.tolist(), srid=srid)
        except ValueError:
            message = "Cannot clean track data: invalid distance values."
            logger.error(message, exc_info=True)
            raise ValueError(message)
        data.drop(columns=["geom"], inplace=True)
        self.data = data.fillna(value=0)

        if commit:
            self.save(update_fields=["data", "geom"])

    def calculate_gradients(self, max_gradient: float, commit=True):
        """
        calculate gradients in percents based on altitude and distance
        while cleaning up bad values.
        """
        data = self.data.copy()
        data["geom"], srid = self.geom, self.geom.srid

        # calculate gradients
        data["gradient"] = data.altitude.diff() / data.distance.diff() * 100

        # find rows with offending gradients
        bad_rows = data[
            (data["gradient"] < -max_gradient) | (data["gradient"] > max_gradient)
        ]

        # drop bad rows and recalculate until all offending values have been removed
        while not bad_rows.empty:
            data.drop(bad_rows.index, inplace=True)
            data["gradient"] = data.altitude.diff() / data.distance.diff() * 100
            bad_rows = data[
                (data["gradient"] < -max_gradient) | (data["gradient"] > max_gradient)
            ]

        # save the values back to the track object
        try:
            self.geom = LineString(data.geom.tolist(), srid=srid)
        except ValueError:
            message = "Cannot clean track data: invalid altitude values."
            logger.error(message, exc_info=True)
            raise ValueError(message)
        data.drop(columns=["geom"], inplace=True)
        self.data = data.fillna(value=0)

        if commit:
            self.save(update_fields=["data", "geom"])

    def calculate_cumulative_elevation_differences(self, commit=True):
        """
        Calculates two columns from the altitude data:
        - cumulative_elevation_gain: cumulative sum of positive elevation data
        - cumulative_elevation_loss: cumulative sum of negative elevation data
        """

        # only consider entries where altitude difference is greater than 0
        self.data["cumulative_elevation_gain"] = self.data.altitude.diff()[
            self.data.altitude.diff() >= 0
        ].cumsum()

        # only consider entries where altitude difference is less than 0
        self.data["cumulative_elevation_loss"] = self.data.altitude.diff()[
            self.data.altitude.diff() <= 0
        ].cumsum()

        # Fill the NaNs with the last valid value of the series
        # then, replace the remaining NaN (at the beginning) with 0
        self.data[["cumulative_elevation_gain", "cumulative_elevation_loss"]] = (
            self.data[["cumulative_elevation_gain", "cumulative_elevation_loss"]]
            .fillna(method="ffill")
            .fillna(value=0)
        )

        if commit:
            self.save(update_fields=["data"])

    def add_distance_and_elevation_totals(self, commit=True):
        """
        add total distance and total elevation gain to every row
        """
        self.data["total_distance"] = self.total_distance
        self.data["total_elevation_gain"] = self.total_elevation_gain

        if commit:
            self.save(update_fields=["data"])

    def update_permanent_track_data(
        self, min_step_distance=1, max_gradient=100, commit=True, force=False
    ):
        """
        calculate unvarying data columns and save them
        """
        track_data_updated = False

        # make sure we have step distances
        if "step_distance" not in self.data.columns or force:
            track_data_updated = True
            self.calculate_step_distances(min_distance=min_step_distance, commit=False)

        # make sure we have step gradients
        if "gradient" not in self.data.columns or force:
            track_data_updated = True
            self.calculate_gradients(max_gradient=max_gradient, commit=False)

        # make sure we have cumulative elevation differences
        if (
            not all(
                column in self.data.columns
                for column in ["cumulative_elevation_gain", "cumulative_elevation_loss"]
            )
            or force
        ):
            track_data_updated = True
            self.calculate_cumulative_elevation_differences(commit=False)

        # make sure we have distance and elevation totals
        if (
            not all(
                column in self.data.columns
                for column in ["total_distance", "total_elevation_gain"]
            )
            or force
        ):
            track_data_updated = True
            self.add_distance_and_elevation_totals(commit=False)

        # commit changes to the database if any
        if track_data_updated and commit:
            self.save(update_fields=["data", "geom"])

    def update_track_details_from_data(self, commit=True):
        """
        set track details from the track data,
        usually replacing remote information received for the route
        """
        if not all(
            column in ["cumulative_elevation_gain", "cumulative_elevation_loss"]
            for column in self.data.columns
        ):
            self.calculate_cumulative_elevation_differences(commit=False)

        # update total_distance, total_elevation_gain and total_elevation_loss from data
        self.total_distance = self.data.distance.max()
        self.total_elevation_loss = abs(self.data.cumulative_elevation_loss.min())
        self.total_elevation_gain = self.data.cumulative_elevation_gain.max()

        if commit:
            self.save(
                update_fields=[
                    "total_distance",
                    "total_elevation_loss",
                    "total_elevation_gain",
                ]
            )

    def get_prediction_model(self, user):
        """
        retrieve performance parameters for user and activity type,
        fallback on activity type if missing and return prediction model.
        """
        if user.is_authenticated:
            performance = ActivityPerformance.objects
            performance = performance.filter(athlete=user.athlete)
            performance = performance.filter(activity_type=self.activity_type)

        if user.is_authenticated and performance.exists():
            # we have performance values for this athlete and activity
            performance = performance.get()

        else:
            # no user performance: fallback on activity_type defaults
            performance = self.activity_type

        return PredictionModel(
            regression_coefficients=performance.regression_coefficients,
            regression_intercept=performance.flat_parameter,
            onehot_encoder_categories=[
                performance.gear_categories,
                performance.workout_type_categories,
            ],
        )

    def calculate_projected_time_schedule(self, user, workout_type=None, gear=None):
        """
        Calculates route pace and route schedule based on the athlete's prediction model
        for the route's activity type.
        """
        # make sure we have all required data columns
        self.update_permanent_track_data(min_step_distance=1, max_gradient=100)

        # add temporary columns useful to the schedule calculation
        data = self.data

        # add gear and workout type to every row
        data["gear"] = gear or "None"
        data["workout_type"] = workout_type or "None"

        # restore prediction model for athlete and activity_type
        prediction_model = self.get_prediction_model(user)

        # keep model pipelines and columns in local variable for readability
        pipeline = prediction_model.pipeline
        numerical_columns = prediction_model.numerical_columns
        categorical_columns = prediction_model.categorical_columns
        feature_columns = numerical_columns + categorical_columns

        data["pace"] = pipeline.predict(data[feature_columns])
        data["schedule"] = (data.pace * data.step_distance).cumsum().fillna(value=0)

        self.data = data

    def get_data(self, line_location, data_column):
        """
        interpolate the value of a given column in the DataFrame
        based on the line_location and the total_distance column.
        """

        # calculate the distance value to interpolate with
        # based on line location and the total length of the track.
        interp_x = line_location * self.total_distance

        # interpolate the value, see:
        # https://docs.scipy.org/doc/numpy/reference/generated/numpy.interp.html
        return interp(interp_x, self.data["distance"], self.data[data_column])

    def get_distance_data(self, line_location, data_column, absolute=False):
        """
        wrap around the get_data method
        to return a Distance object.
        """
        distance_data = self.get_data(line_location, data_column)

        # return distance object
        if distance_data is not None:
            return D(m=abs(distance_data)) if absolute else D(m=distance_data)

    def get_time_data(self, line_location, data_column):
        """
        wrap around the get_data method
        to return a timedelta object.
        """
        time_data = self.get_data(line_location, data_column)
        # return time object
        if time_data is not None:
            return timedelta(seconds=int(time_data))

    def get_start_altitude(self):
        start_altitude = self.get_distance_data(0, "altitude")
        return start_altitude

    def get_end_altitude(self):
        end_altitude = self.get_distance_data(1, "altitude")
        return end_altitude

    def get_total_distance(self):
        """
        returns track total_distance as a Distance object
        """
        return D(m=self.total_distance)

    def get_total_elevation_gain(self):
        """
        returns total altitude gain as a Distance object
        """
        return D(m=self.total_elevation_gain)

    def get_total_elevation_loss(self):
        """
        returns total altitude loss as a Distance object
        """
        return D(m=self.total_elevation_loss)

    def get_total_duration(self):
        """
        returns total duration as a timedelta object
        """
        return self.get_time_data(1, "schedule")

    def get_closest_places_along_line(self, line_location=0, max_distance=200):
        """
        retrieve Place objects with a given distance of a point on the line.
        """
        # create the point from location
        point = self.geom.interpolate_normalized(line_location)

        # get closest places to the point
        places = get_places_within(point, max_distance)

        return places

    def get_start_places(self, max_distance=200):
        """
        retrieve Place objects close to the start of the track.
        """
        return self.get_closest_places_along_line(
            line_location=0, max_distance=max_distance
        )

    def get_end_places(self, max_distance=200):
        """
        retrieve Place objects close to the end of the track.
        """
        return self.get_closest_places_along_line(
            line_location=1, max_distance=max_distance
        )
