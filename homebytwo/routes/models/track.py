from datetime import timedelta

from django.contrib.gis.db import models
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.measure import D

from easy_thumbnails.fields import ThumbnailerImageField
from numpy import interp

from ...core.models import TimeStampedModel
from ...core.utils import get_image_path
from ..fields import DataFrameField
from ..utils import get_places_within
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
    totalup = models.FloatField("Total elevation gain in m", default=0)

    # elevation loss in m
    totaldown = models.FloatField("Total elevation loss in m", default=0)

    # route distance in m
    length = models.FloatField("Total length of the track in m", default=0)

    # geographic information
    geom = models.LineStringField("line geometry", srid=21781)

    # Start and End-place
    start_place = models.ForeignKey(
        Place, null=True, related_name="starts_%(class)s", on_delete=models.SET_NULL
    )

    end_place = models.ForeignKey(
        Place, null=True, related_name="ends_%(class)s", on_delete=models.SET_NULL
    )

    # track data as a pandas DataFrame
    data = DataFrameField(null=True, max_length=100, save_to="data")

    def calculate_elevation_gain_and_distance(self):
        """
        calculate the gain and distance columns of the data Dataframe.
        """

        data = self.data

        # calculate distance between each point
        data["distance"] = data["length"].diff().fillna(value=0)

        # calculate elevation gain between each point
        data["gain"] = data["altitude"].diff().fillna(value=0)

        self.data = data

    def calculate_cummulative_elevation_differences(self):
        """
        Calculates two colums from the altitude data:
        - totalup: cummulative sum of positive elevation data
        - totaldown: cummulative sum of negative elevation data
        """
        data = self.data

        # only consider entries where altitude difference is greater than 0
        data["totalup"] = data["altitude"].diff()[data["altitude"].diff() >= 0].cumsum()

        # only consider entries where altitude difference is less than 0
        data["totaldown"] = (
            data["altitude"].diff()[data["altitude"].diff() <= 0].cumsum()
        )

        # Fill the NaNs with the last valid value of the series
        # then, replace the remainng NaN (at the beginning) with 0
        data[["totalup", "totaldown"]] = (
            data[["totalup", "totaldown"]].fillna(method="ffill").fillna(value=0)
        )

        self.data = data

    def get_performance_data(self, athlete):
        """
        retrieve performance parameters for activity type
        """
        activity_type = self.activity_type

        if athlete.user.is_authenticated:
            performance = ActivityPerformance.objects
            performance = performance.filter(athlete=athlete)
            performance = performance.filter(activity_type=activity_type)

        if athlete.user.is_authenticated and performance.exists():
            # we have performance values for this athlete and activity
            performance = performance.get()

        else:
            # no user performance: fallback on activity defaults
            performance = activity_type

        return performance

    def calculate_projected_time_schedule(self, athlete):
        """
        Calculates a time schedule based on activity, user performance,
        and total elevation gain.

        The pace of the athlete depends on the slope of the travelled terrain.
        we estimate a polynomial equation for the pace.

            pace = slope_param_squared * slope**2 +
                   slope_param * slope +
                   flat_pace_param +
                   total_elevation_gain_param * total_elevation_gain

        Where the pace in s/m and slope_param_squared, slope_param,
        flat_pace_param and total_elevation_gain_param are variables fitted
        with a polynomial linear regression from past Strava performances.

            pace = time / distance
            slope = elevation_gain / distance

        We solve for time:

        time = (slope_param_squared * elevation_gain**2 / distance) +
                slope_param * elevation_gain +
                flat_pace_param * distance +
                total_elevation_gain_param * total_elevation_gain * distance

        total_elevation_gain_param * total_elevation_gain is added to account for the total effort.

        """

        data = self.data

        # make sure we have elevation gain and distance data
        if not all(column in ["gain", "distance"] for column in list(data)):
            self.calculate_elevation_gain_and_distance()

        # get performance data for athlete and activity
        performance = self.get_performance_data(athlete)

        # set performance parameters
        slope_squared_param = performance.slope_squared_param
        slope_param = performance.slope_param
        flat_param = performance.flat_param
        total_elevation_gain_param = performance.total_elevation_gain_param

        # Calculate schedule, ignoring segments where distance is 0
        data["schedule"] = (
            (
                (slope_squared_param * data["gain"] ** 2) / data["distance"]
                + slope_param * data["gain"]
                + flat_param * data["distance"]
                + total_elevation_gain_param * data["totalup"] / 1000 * data["distance"]
            )
            .where(data["distance"] > 0.1, 0)
            .cumsum()
            .fillna(value=0)
        )

        self.data = data

    def get_data(self, line_location, data_column):
        """
        interpolate the value of a given column in the DataFrame
        based on the line_location and the distance column.
        """
        # return none if data field is empty
        if self.data is None:
            return None

        # calculate the distance value to interpolate with
        # based on line location and the total length of the track.
        interp_x = line_location * self.length

        # interpolate the value, see:
        # https://docs.scipy.org/doc/numpy/reference/generated/numpy.interp.html
        return interp(interp_x, self.data["length"], self.data[data_column])

    def get_distance_data(self, line_location, data_column):
        """
        wrap around the get_data method
        to return a Distance object.
        """
        distance_data = self.get_data(line_location, data_column)

        # return distance object
        if distance_data is not None:
            return D(m=distance_data)

        return

    def get_time_data(self, line_location, data_column):
        """
        wrap around the get_data method
        to return a timedelta object.
        """
        time_data = self.get_data(line_location, data_column)
        # return time object
        if time_data is not None:
            return timedelta(seconds=int(time_data))

        return

    def get_start_altitude(self):
        start_altitude = self.get_distance_data(0, "altitude")
        return start_altitude

    def get_end_altitude(self):
        end_altitude = self.get_distance_data(1, "altitude")
        return end_altitude

    def get_start_point(self):
        return GEOSGeometry("POINT (%s %s)" % self.geom[0], srid=21781)

    def get_end_point(self):
        return GEOSGeometry("POINT (%s %s)" % self.geom[-1], srid=21781)

    def get_length(self):
        """
        returns track length as a Distance object
        """
        return D(m=self.length)

    def get_totalup(self):
        """
        returns cummalive altitude gain as a Distance object
        """
        return D(m=self.totalup)

    def get_totaldown(self):
        """
        returns cummalive altitude loss as a Distance object
        """
        return D(m=self.totaldown)

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
