from django.conf import settings

from django.contrib.gis.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .place import Place
from django.contrib.gis.measure import D
from django.utils.translation import gettext_lazy as _

from datetime import timedelta
from math import floor, ceil
from pandas import read_hdf, DataFrame
import uuid
import os

import pandas as pd


class DataFrameField(models.CharField):
    """
    Custom Filefield to save the DataFramen to the hdf5 file format as adviced
    here: http://pandas.pydata.org/pandas-docs/stable/io.html#io-perf
    """
    default_error_messages = {
        'invalid': _('Please provide a DataFrame object'),
        'io_error': _('Could not write to file')
    }

    def __init__(self, max_length, save_to='', *args, **kwargs):
        self.save_to = save_to
        self.max_length = max_length
        super(DataFrameField, self).__init__(
            max_length=max_length, *args, **kwargs)

    def generate_unique_filename(self):
        """
        generate a unique filename for the saved file.
        """
        filename = uuid.uuid4().hex + '.h5'

        return filename

    def write_hdf5(self, data, filename):
        dirname = os.path.join(
            settings.BASE_DIR,
            settings.MEDIA_ROOT,
            self.save_to
        )

        fullpath = os.path.join(dirname, filename)

        if not isinstance(data, DataFrame):
            raise ValidationError(
                self.error_messages['invalid'],
                code='invalid',
            )

        if not os.path.exists(dirname):
            os.makedirs(dirname)

        try:
            data.to_hdf(fullpath, 'df', mode='w', format='fixed')
        except Exception as exc:
            raise IOError(
                self.error_messages['io_error']
            ) from exc

        return fullpath

    def json(self, data):
        """
        Writes a json object
        """
        return data.to_json(orient='records')

    def read_json(self, json):
        return pd.read_json(json, orient='records')

    def get_prep_value(self, value):
        """
        let's save the DataFrame as a file with in the MEDIA_ROOT folder
        and put the filename in the valuebase.
        """
        if value is None:
            return value

        if not isinstance(value, DataFrame):
            raise ValidationError(
                self.error_messages['invalid'],
                code='invalid',
            )

        # if the valueframe was loaded from the database before,
        # it will has a filename attribute.
        if hasattr(value, 'filename'):
            filename = value.filename

        else:
            # create a new filename
            filename = self.generate_unique_filename()

        self.write_hdf5(value, filename)

        return filename

    def to_python(self, filename):
        """
        get the file location from the database
        and load the DataFrame from the file.
        """
        dirname = os.path.join(
            settings.BASE_DIR,
            settings.MEDIA_ROOT,
            self.save_to
        )

        fullpath = os.path.join(dirname, filename)

        # try to load the pandas DataFrame into memory
        try:
            data = read_hdf(fullpath)

        except Exception:
            raise

        if not isinstance(data, DataFrame):
            raise ValidationError(
                self.error_messages['invalid'],
                code='invalid',
            )

        # set attribute on for saving later
        data.filename = filename

        return data


class Track(models.Model):

    class Meta:
        abstract = True

    name = models.CharField(max_length=100)
    description = models.TextField('Textual description', default='')

    # link to user
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # elevation gain in m
    totalup = models.FloatField('Total elevation gain in m', default=0)
    # elevation loss in m
    totaldown = models.FloatField('Total elevation loss in m', default=0)
    # route distance in m
    length = models.FloatField('Total length of the track in m', default=0)

    # creation and update date
    updated = models.DateTimeField('Time of last update', auto_now=True)
    created = models.DateTimeField('Time of creation', auto_now_add=True)

    # geographic information
    geom = models.LineStringField('line geometry', srid=21781)

    # Start and End-place
    start_place = models.ForeignKey(
        Place,
        null=True,
        related_name='starts_%(class)s'
    )

    end_place = models.ForeignKey(
        Place,
        null=True,
        related_name='ends_%(class)s'
    )

    # track data as a pandas DataFrame
    data = DataFrameField(null=True, max_length=100, save_to='data')

    def calculate_cummulative_elevation_differences(self):
        """
        Calculates two colums from the altitude data:
        - total_up: cummulative sum of positive elevation data
        - total_down: cummulative sum of negative elevation data
        """
        data = self.data

        # add or update total_up and total_down columns based on altitude data
        data['total_up'] = data['altitude'].\
            diff()[data['altitude'].diff() >= 0].cumsum()

        data['total_down'] = data['altitude'].\
            diff()[data['altitude'].diff() <= 0].cumsum()

        # replace NaN with the last valid value of the series
        # then, replace the remainng NaN (at the beginning) with 0
        data[['total_up', 'total_down']] = data[['total_up', 'total_down']]. \
            fillna(method='ffill').fillna(value=0)

        self.data = data

    def calculate_projected_time_schedule(self):
        """
        Calculates a time schedule based on activity, distance and
        elevation gain/loss.
        """

        data = self.data

        # flat pace as second per meter
        flat_pace = 3600/4000  # 1 hour for 4km = 0.9s for each m

        # pace going up as second per meter
        up_pace = 3600/400  # 1 hour for 400m up = 9s for each m

        # flat distance / flat_speed + elevation_gain / up_speed
        data['schedule'] = (
            (data['length'] * flat_pace)
            + (data['total_up'] * up_pace)
        )

        self.data = data

    # Returns poster picture for the list view
    def get_data_from_line_location(self, line_location, column):
        """
        return the index of a row in the DataFrame
        based on the line_location.
        """

        # get the number of rows in the data
        nb_rows, nb_columns = self.data.shape

        # interpolate the position in the data series
        float_index = line_location * (nb_rows - 1)

        # find the previous value in the series
        previous_index = floor(float_index)
        previous_value = self.data.iloc[previous_index][column]

        # find the next index in the series
        next_index = ceil(float_index)
        next_value = self.data.iloc[next_index][column]

        # calculate the weighting of the previous value
        weight = float_index - previous_index

        value = (previous_value * weight) + ((1-weight) * next_value)

        return value

    def get_distance_data_from_line_location(self, line_location, data_column):
        """
        wrap around the get_data_from_line_location method
        to return a Distance object.
        """
        distance_data = self.get_data_from_line_location(
            line_location,
            data_column
        )

        # return distance object
        return D(m=distance_data)

    def get_time_data_from_line_location(self, line_location, data_column):
        """
        wrap around the get_data_from_line_location method
        to return a timedelta object.
        """
        time_data = self.get_data_from_line_location(
            line_location,
            data_column
        )

        # return distance object
        return timedelta(seconds=int(time_data))

    def get_start_altitude(self):
        start_altitude = self.get_distance_data_from_line_location(
            0, 'altitude')
        return start_altitude

    def get_end_altitude(self):
        end_altitude = self.get_distance_data_from_line_location(
            1, 'altitude')
        return end_altitude

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

    def get_closest_places_along_line(self, line_location=0, max_distance=100):

        # create the point from location
        point = self.geom.interpolate_normalized(line_location)

        # get closest places to the point
        places = Place.objects.get_places_within(point, max_distance)

        return places
