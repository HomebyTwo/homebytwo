import os
import uuid
from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.measure import D
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from easy_thumbnails.fields import ThumbnailerImageField
from numpy import interp
from pandas import DataFrame, read_hdf, read_json

from . import ActivityPerformance, ActivityType, Place


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


def get_image_path(instance, filename):
    """
    callable to define the image upload path according
    to the type of object: segment, route, etc.. and the id of the object.
    """
    return os.path.join(
        'images',
        instance.__class__.__name__,
        str(instance.id),
        filename
    )


class Track(models.Model):

    class Meta:
        abstract = True

    name = models.CharField(max_length=100)
    description = models.TextField('Textual description', blank=True)
    image = ThumbnailerImageField(upload_to=get_image_path,
                                  blank=True, null=True)

    # Main activity of the track: default=hike
    activity_type = models.ForeignKey(ActivityType, default=1,
                                      on_delete=models.SET_DEFAULT)

    # link to user
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # elevation gain in m
    totalup = models.FloatField(
        'Total elevation gain in m',
        default=0
    )
    # elevation loss in m
    totaldown = models.FloatField(
        'Total elevation loss in m',
        default=0
    )
    # route distance in m
    length = models.FloatField(
        'Total length of the track in m',
        default=0
    )

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

    def is_owner(self):
        """
        determines wether a route is owned by the currently logged in user
        """
        return True

    def calculate_elevation_gain_and_distance(self):
        """
        calculate the gain and distance columns of the data Dataframe.
        """

        data = self.data

        # calculate distance between each point
        ['distance'] = data['length'].diff()

        # cleanup cases where the distance is 0
        data = data[data.distance > 0]

        # calculate elevation gain between each point
        data['gain'] = data['altitude'].diff()

        return data

    def calculate_cummulative_elevation_differences(self):
        """
        Calculates two colums from the altitude data:
        - totalup: cummulative sum of positive elevation data
        - totaldown: cummulative sum of negative elevation data
        """
        data = self.data

        # only consider entries where altitude difference is greater than 0
        data['totalup'] = data['altitude'].diff()[
            data['altitude'].diff() >= 0
        ].cumsum()

        # only consider entries where altitude difference is less than 0
        data['totaldown'] = data['altitude'].diff()[
            data['altitude'].diff() <= 0
        ].cumsum()

        # Fill the NaNs with the last valid value of the series
        # then, replace the remainng NaN (at the beginning) with 0
        data[['totalup', 'totaldown']] = data[['totalup', 'totaldown']].\
            fillna(method='ffill').fillna(value=0)

        self.data = data

    def get_performance_data(self, user):
        """
        retrieve pèrformance parameters for activity type
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

    def calculate_projected_time_schedule(self, user):
        """
        Calculates a time schedule based on activity, user performance,
        and total elevation gain.

        The pace of the athlete depends on the slope of the travelled terrain.
        we estimate a polynomial equation for the pace.

            pace = slope_param_squared * slope**2 +
                   slope_param * slope +
                   flat_pace_param +
                   total_elevation_gain_param * total_elevation_gain

        Where the is pace in s/m and slope_param_squared, slope_param,
        flat_pace_param and total_elevation_gain_param are variables fitted
        with a polynomial linear regression from past Strava performances.

            pace = time / distance
            slope = elevation_gain / distance

        We solve for time:

        time = (slope_param_squared * elevation_gain**2 / distance) +
                slope_param * elevation_gain +
                flat_pace_param * distance +
                total_elevation_gain_param * total_elevation_gain * distance

        total_elevation_gain_param * total_elevation_gain is constant.
        let's call it totalup_penalty.

        """

        data = self.data

        # make sure we have elevation gain and distance data
        if not all(column in ['gain', 'distance'] for column in list(data)):
            data = self.calculate_elevation_gain_and_distance()

        # get performance data for atrhlete and activity
        performance = self.get_performance_data(user)

        # set performance parameters
        slope_squared_param = performance.slope_squared_param
        slope_param = performance.slope_param
        flat_param = performance.flat_param

        # calculate totalup_penalty
        total_elevation_gain_param = performance.total_elevation_gain_param
        total_elevation_gain = self.get_totalup().km

        totalup_penalty = total_elevation_gain_param * total_elevation_gain

        data['schedule'] = (
            (slope_squared_param * data['gain']**2)/data['distance']
            + slope_param * data['gain']
            + flat_param * data['distance']
            + totalup_penalty * data['distance']
        ).cumsum()

        data['schedule'] = data['schedule'].fillna(value=0)

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
        return interp(interp_x, self.data['length'], self.data[data_column])

    def get_distance_data(self, line_location, data_column):
        """
        wrap around the get_data method
        to return a Distance object.
        """
        distance_data = self.get_data(
            line_location,
            data_column
        )

        # return distance object
        if distance_data is not None:
            return D(m=distance_data)

        return

    def get_time_data(self, line_location, data_column):
        """
        wrap around the get_data method
        to return a timedelta object.
        """
        time_data = self.get_data(
            line_location,
            data_column
        )
        # return time object
        if time_data is not None:
            return timedelta(seconds=int(time_data))

        return

    def get_start_altitude(self):
        start_altitude = self.get_distance_data(
            0, 'altitude')
        return start_altitude

    def get_end_altitude(self):
        end_altitude = self.get_distance_data(
            1, 'altitude')
        return end_altitude

    def get_start_point(self):
        return GEOSGeometry('POINT (%s %s)' % self.geom[0], srid=21781)

    def get_end_point(self):
        return GEOSGeometry('POINT (%s %s)' % self.geom[-1], srid=21781)

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
        return self.get_time_data(1, 'schedule')

    def get_closest_places_along_line(self, line_location=0, max_distance=100):
        # create the point from location
        point = self.geom.interpolate_normalized(line_location)

        # get closest places to the point
        places = Place.objects.get_places_within(point, max_distance)

        return places
