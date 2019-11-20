import os
from uuid import uuid4

from django import forms
from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import ValidationError
from django.db import connection
from django.utils.translation import gettext_lazy as _

from pandas import DataFrame, read_hdf, read_json


def LineSubstring(line, start_location, end_location):
    """
    implements ST_Line_Substring
    """
    sql = (
        "SELECT ST_AsText(ST_Line_SubString("
        "ST_GeomFromText(%(line)s, %(srid)s), %(start)s, %(end)s));"
    )

    with connection.cursor() as cursor:
        cursor.execute(
            sql,
            {
                "line": line.wkt,
                "srid": line.srid,
                "start": start_location,
                "end": end_location,
            },
        )
        geom = cursor.fetchone()[0]

    return GEOSGeometry(geom)


class DataFrameField(models.CharField):
    """
    Custom Filefield to save Pandas DataFrame to the hdf5 file format
    as advised in the official pandas documentation:
    http://pandas.pydata.org/pandas-docs/stable/io.html#io-perf
    """

    default_error_messages = {
        "invalid": _("Please provide a DataFrame object"),
        "io_error": _("Could not write to file"),
    }

    def __init__(self, max_length, save_to="data", *args, **kwargs):
        self.save_to = save_to
        self.max_length = max_length
        super(DataFrameField, self).__init__(max_length=max_length, *args, **kwargs)

    def _generate_unique_filename(self):
        """
        generate a unique filename for the saved file.
        """
        filename = uuid4().hex + ".h5"

        return filename

    def _write_hdf5(self, data, filename):
        """
        write the file to the media directory. This should be improved
        to use the storage instead of using os methods.
        I just could not figure out how to do it with pandas' to_hdf method.
        """
        dirname = os.path.join(settings.BASE_DIR, settings.MEDIA_ROOT, self.save_to)

        fullpath = os.path.join(dirname, filename)

        if not isinstance(data, DataFrame):
            raise ValidationError(
                self.error_messages["invalid"], code="invalid",
            )

        if not os.path.exists(dirname):
            os.makedirs(dirname)

        try:
            data.to_hdf(fullpath, "df", mode="w", format="fixed")
        except Exception as exc:
            raise IOError(self.error_messages["io_error"]) from exc

        return fullpath

    def _parse_filename(self, filename):
        dirname = os.path.join(settings.BASE_DIR, settings.MEDIA_ROOT, self.save_to)

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
                self.error_messages["invalid"], code="invalid",
            )

        # if the valueframe was loaded from the database before,
        # it will has a filename attribute.
        if hasattr(value, "filename"):
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
                self.error_messages["invalid"], code="invalid",
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
                if hasattr(e, "code") and e.code in self.error_messages:
                    e.message = self.error_messages[e.code]
                    errors.extend(e.error_list)
        if errors:
            raise ValidationError(errors)

    def formfield(self, **kwargs):
        defaults = {"form_class": DataFrameFormField}
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
                return value.to_json(orient="records") if value is not None else ""
            except ValueError:
                raise ValidationError(
                    _("Could serialize '%(value)s' to json."),
                    code="invalid",
                    params={"value": value},
                )

        return value if value not in self.empty_values else ""

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
                return read_json(value, orient="records")
            except ValueError:
                raise ValidationError(
                    _("Could not read json: '%(value)s' into a DataFrame."),
                    code="invalid",
                    params={"value": value},
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
                code="invalid",
                params={"value": value},
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
                if hasattr(e, "code") and e.code in self.error_messages:
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

        initial_value = initial if initial is not None else ""
        data_value = data if data is not None else ""

        if isinstance(initial_value, DataFrame) and isinstance(data_value, DataFrame):
            try:
                return (initial_value != data_value).any().any()
            except ValueError:
                return True

        if not isinstance(initial_value, DataFrame) and not isinstance(
            data_value, DataFrame
        ):
            return initial_value != data_value

        return True
