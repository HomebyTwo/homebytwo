from datetime import timedelta
from uuid import uuid4

from django.contrib.gis.db import models
from django.contrib.gis.measure import D

from easy_thumbnails.fields import ThumbnailerImageField
from numpy import array, interp

from ...core.models import TimeStampedModel
from ..fields import DataFrameField
from ..prediction_model import PredictionModel
from ..utils import get_image_path, get_places_within
from . import ActivityPerformance, ActivityType, Place


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
    data = DataFrameField(null=True, upload_to="data", unique_fields=["uuid"])

    def update_track_details_from_data(self):
        """
        set track details from the track data,
        usually replacing remote information received for the route
        """
        if not all(
            column in ["total_elevation_gain", "total_elevation_loss"]
            for column in self.data.columns
        ):
            self.calculate_cummulative_elevation_differences()

        # update total_distance, total_elevation_gain and total_elevation_loss from data
        self.total_distance = self.data.distance.max()
        self.total_elevation_loss = abs(self.data.cummulative_elevation_loss.min())
        self.total_elevation_gain = self.data.cummulative_elevation_gain.max()

    def calculate_gradient_and_distance(self):
        """
        add gradient and distance between each point of the track data.
        """
        # calculate distance between each point
        self.data["step_distance"] = self.data.distance.diff().fillna(value=0)

        # calculate slope percentage between each point
        self.data["gradient"] = (
            self.data.altitude.diff() / self.data.step_distance * 100
        ).fillna(value=0)

    def calculate_cummulative_elevation_differences(self):
        """
        Calculates two colums from the altitude data:
        - cummulative_elevation_gain: cummulative sum of positive elevation data
        - cummulative_elevation_loss: cummulative sum of negative elevation data
        """
        data = self.data

        # only consider entries where altitude difference is greater than 0
        data["cummulative_elevation_gain"] = (
            data["altitude"].diff()[data["altitude"].diff() >= 0].cumsum()
        )

        # only consider entries where altitude difference is less than 0
        data["cummulative_elevation_loss"] = (
            data["altitude"].diff()[data["altitude"].diff() <= 0].cumsum()
        )

        # Fill the NaNs with the last valid value of the series
        # then, replace the remainng NaN (at the beginning) with 0
        data[["cummulative_elevation_gain", "cummulative_elevation_loss"]] = (
            data[["cummulative_elevation_gain", "cummulative_elevation_loss"]]
            .fillna(method="ffill")
            .fillna(value=0)
        )

        self.data = data

    def get_performance_data(self, user):
        """
        retrieve performance parameters for activity type
        """
        activity_type = self.activity_type

        if user.is_authenticated:
            performance = ActivityPerformance.objects
            performance = performance.filter(athlete=user.athlete)
            performance = performance.filter(activity_type=activity_type)

        if user.is_authenticated and performance.exists():
            # we have performance values for this athlete and activity
            performance = performance.get()

        else:
            # no user performance: fallback on activity defaults
            performance = activity_type

        return performance

    def calculate_projected_time_schedule(self, user, workout_type="None", gear="None"):
        """
        Calculates route pace and route schedule based on the athlete's prediction model
        for the route's activity type.
        """

        data = self.data

        # make sure we have cummulative elevation differences
        if not all(
            column in ["total_elevation_gain", "total_elevation_loss"]
            for column in data.columns
        ):
            self.calculate_cummulative_elevation_differences()

        # make sure we have elevation gain and distance data
        if not all(column in ["gradient", "step_distance"] for column in data.columns):
            self.calculate_gradient_and_distance()

        # keep the first row but ignore rows where step_distance is shorter than 1m
        first_row = data[data["distance"].diff().isnull()]
        data = first_row.append(data[data["step_distance"] > 1])

        # add route totals to every row
        data["total_distance"] = max(data["distance"])
        data["total_elevation_gain"] = max(data["cummulative_elevation_gain"])

        # add gear and workout type to every row
        data["gear"] = gear
        data["workout_type"] = workout_type

        # retrieve performance data for athlete and activity_type
        performance = self.get_performance_data(user)

        # restore prediction model with performance parameters
        prediction_model = PredictionModel(
            regression_coefficients=performance.regression_coefficients,
            regression_intercept=performance.flat_parameter,
            onehot_encoder_categories=[
                array([item for item in category_list if item])
                for category_list in performance.onehot_encoder_categories
            ],
        )

        # keep model pipelines and columns in local variable for readability
        pipeline = prediction_model.pipeline
        numerical_columns = prediction_model.numerical_columns
        categorical_columns = prediction_model.categorical_columns
        feature_columns = numerical_columns + categorical_columns

        data["pace"] = pipeline.predict(data[feature_columns])
        data["schedule"] = data.pace * data.step_distance.cumsum().fillna(value=0)

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

    def get_distance_data(self, line_location, data_column):
        """
        wrap around the get_data method
        to return a Distance object.
        """
        distance_data = self.get_data(line_location, data_column)

        # return distance object
        if distance_data is not None:
            return D(m=distance_data)

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
        returns cummalive altitude gain as a Distance object
        """
        return D(m=self.total_elevation_gain)

    def get_total_elevation_loss(self):
        """
        returns cummalive altitude loss as a Distance object
        """
        return D(m=self.total_elevation_loss)

    def get_total_duration(self):
        """
        returns cummalive altitude loss as a Distance object
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
