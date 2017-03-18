from django import forms
from django.conf import settings

from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.contrib.gis.measure import D
from django.utils.translation import gettext_lazy as _

from . import Place

from datetime import timedelta
from math import floor, ceil
from pandas import read_hdf, read_json, DataFrame
import uuid
import os


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

    def _generate_unique_filename(self):
        """
        generate a unique filename for the saved file.
        """
        filename = uuid.uuid4().hex + '.h5'

        return filename

    def _write_hdf5(self, data, filename):
        """
        write the file to the media directory. This should be improved
        to use the storage instead of using os methods.
        I just could not figure out how to do it with pandas' to_hdf method.
        """
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

    def _parse_filename(self, filename):
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

        # set attribute on for saving later
        data.filename = filename

        return data

    def get_prep_value(self, value):
        """
        save the DataFrame as a file in the MEDIA_ROOT folder
        and put the filename in the database.
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
            filename = self._generate_unique_filename()

        self._write_hdf5(value, filename)

        return filename

    def from_db_value(self, value, expression, connection, context):
        """
        use the filename from the database to load the DataFrame from file.
        """
        if value in self.empty_values:
            return None

        # try to load the pandas DataFrame into memory
        return self._parse_filename(value)

    def to_python(self, value):
        """
        if the value is a Dataframe object, return it.
        otherwise, get the file location from the database
        and load the DataFrame from the file.
        """
        if value is None:
            return value

        if isinstance(value, DataFrame):
            return value

        if isinstance(value, str):
            if value in self.empty_values:
                return None
            return self._parse_filename(value)

    def validate(self, value, model_instance):
        if not isinstance(value, DataFrame):
            raise ValidationError(
                self.error_messages['invalid'],
                code='invalid',
            )

    def run_validators(self, value):
        """
        Because of comparisons of DataFrame,
        the native methode must be overridden.
        """
        if value is None:
            return

        errors = []
        for v in self.validators:
            try:
                v(value)
            except ValidationError as e:
                if hasattr(e, 'code') and e.code in self.error_messages:
                    e.message = self.error_messages[e.code]
                    errors.extend(e.error_list)
        if errors:
            raise ValidationError(errors)

    def formfield(self, **kwargs):
        defaults = {'form_class': DataFrameFormField}
        defaults.update(kwargs)
        return super(DataFrameField, self).formfield(**defaults)


class DataFrameFormField(forms.CharField):

    widget = forms.widgets.HiddenInput

    def prepare_value(self, value):
        """
        serialize DataFrame objects to json using pandas native function.
        for inclusion in forms.
        """
        if isinstance(value, DataFrame):
            try:
                return value.to_json(orient='records') if value is not None else ''
            except:
                raise ValidationError(
                    _("Could serialize '%(value)s' to json."),
                    code='invalid',
                    params={'value': value},
                )

        return value if value not in self.empty_values else ''

    def to_python(self, value):
        """
        convert json values to DataFrame using pandas native function.
        """
        if value is None:
            return None

        if isinstance(value, DataFrame):
            return value

        if isinstance(value, str):
            if value in self.empty_values:
                return None
            try:
                return read_json(value, orient='records')
            except:
                raise ValidationError(
                    _("Could not read json: '%(value)s' into a DataFrame."),
                    code='invalid',
                    params={'value': value},
                )

        return None

    def validate(self, value):
        """
        override validation because DataFrame objects
        suck at being compared. See:
        http://pandas.pydata.org/pandas-docs/stable/gotchas.html#gotchas-truth
        """
        if value is None:
            return

        if not isinstance(value, DataFrame):
            raise ValidationError(
                _("'%(value)s' does not seem to be a DataFrame."),
                code='invalid',
                params={'value': value},
            )

    def run_validators(self, value):
        """
        again, because of comparisons, the native methode must be overridden.
        """
        if value is None:
            return

        errors = []
        for v in self.validators:
            try:
                v(value)
            except ValidationError as e:
                if hasattr(e, 'code') and e.code in self.error_messages:
                    e.message = self.error_messages[e.code]
                    errors.extend(e.error_list)
        if errors:
            raise ValidationError(errors)

    def has_changed(self, initial, data):
        if self.disabled:
            return False
        try:
            data = self.to_python(data)
        except ValidationError:
            return True

        initial_value = initial if initial is not None else ''
        data_value = data if data is not None else ''

        if (isinstance(initial_value, DataFrame) and
                isinstance(data_value, DataFrame)):
            try:
                return (initial_value != data_value).any().any()
            except ValueError:
                return True

        if (not isinstance(initial_value, DataFrame) and
                not isinstance(data_value, DataFrame)):
            return initial_value != data_value

        return True


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
        - totalup: cummulative sum of positive elevation data
        - totaldown: cummulative sum of negative elevation data
        """
        data = self.data

        # add or update totalup and totaldown columns based on altitude data
        data['totalup'] = data['altitude'].\
            diff()[data['altitude'].diff() >= 0].cumsum()

        data['totaldown'] = data['altitude'].\
            diff()[data['altitude'].diff() <= 0].cumsum()

        # replace NaN with the last valid value of the series
        # then, replace the remainng NaN (at the beginning) with 0
        data[['totalup', 'totaldown']] = data[['totalup', 'totaldown']]. \
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
            + (data['totalup'] * up_pace)
        )

        self.data = data

    # Returns poster picture for the list view
    def get_data_from_line_location(self, line_location, data_column):
        """
        return the index of a row in the DataFrame
        based on the line_location.
        """
        # return none if data field is empty
        if self.data is None:
            return None

        # get the number of rows in the data
        nb_rows, nb_columns = self.data.shape

        # interpolate the position in the data series
        float_index = line_location * (nb_rows - 1)

        # find the previous value in the series
        previous_index = floor(float_index)
        previous_value = self.data.iloc[previous_index][data_column]

        # find the next index in the series
        next_index = ceil(float_index)
        next_value = self.data.iloc[next_index][data_column]

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
        if distance_data is not None:
            return D(m=distance_data)

        return

    def get_time_data_from_line_location(self, line_location, data_column):
        """
        wrap around the get_data_from_line_location method
        to return a timedelta object.
        """
        time_data = self.get_data_from_line_location(
            line_location,
            data_column
        )

        # return time object
        if time_data is not None:
            return timedelta(seconds=int(time_data))

        return

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
