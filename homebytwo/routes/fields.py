from inspect import getmro
from pathlib import Path

from django.apps import apps
from django.contrib.gis.db import models
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.postgres.fields import ArrayField
from django.core import checks
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.core.files.storage import default_storage
from django.db import connection
from django.forms import MultipleChoiceField
from django.forms.widgets import CheckboxSelectMultiple
from django.utils.translation import gettext_lazy as _

from numpy import array
from pandas import DataFrame, read_hdf


def LineSubstring(line, start_location, end_location):
    """
    implements ST_Line_Substring
    """
    sql = (
        "SELECT ST_AsText(ST_LineSubstring("
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
    custom field to save Pandas DataFrame to the hdf5 file format
    as advised in the official pandas documentation:
    http://pandas.pydata.org/pandas-docs/stable/io.html#io-perf
    """

    attr_class = DataFrame

    default_error_messages = {
        "invalid": _("Please provide a DataFrame object"),
    }

    def __init__(
        self,
        verbose_name=None,
        name=None,
        upload_to="data",
        storage=None,
        unique_fields=[],
        **kwargs,
    ):

        self.storage = storage or default_storage
        self.upload_to = upload_to
        self.unique_fields = unique_fields

        kwargs.setdefault("max_length", 100)
        super().__init__(verbose_name, name, **kwargs)

    def check(self, **kwargs):
        return [
            *super().check(**kwargs),
            *self._check_unique_fields(**kwargs),
        ]

    def _check_unique_fields(self, **kwargs):
        if not isinstance(self.unique_fields, list) or self.unique_fields == []:
            return [
                checks.Error(
                    "you must provide a list of unique fields.",
                    obj=self,
                    id="homebytwo.E001",
                )
            ]

        for field in getattr(self, "unique_fields"):
            try:
                self.model._meta.get_field(field)
            except FieldDoesNotExist as error:
                return [
                    checks.Error(
                        "unique_fields is badly set: {}".format(error),
                        obj=self,
                        id="homebytwo.E002",
                    )
                ]
        return []

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if kwargs.get("max_length") == 100:
            del kwargs["max_length"]
        if self.upload_to != "data":
            kwargs["upload_to"] = self.upload_to
        if self.storage is not default_storage:
            kwargs["storage"] = self.storage
        kwargs["unique_fields"] = self.unique_fields
        return name, path, args, kwargs

    def from_db_value(self, value, expression, connection):
        """
        return a DataFrame object from the filepath saved in DB
        """
        if value is None:
            return value

        return self.retrieve_dataframe(value)

    def get_relative_path(self, value):
        """
        return file path based on the value saved in the Database.
        prepend filepath to older objects that were saved without it.
        """
        *dirs, filename = Path(value).parts
        dirs = dirs or [self.upload_to]
        return Path(*dirs, filename)

    def get_absolute_path(self, value):
        """
        return absolute path based on the value saved in the Database.
        """
        filepath = self.get_relative_path(value)

        # return absolute path
        return self.storage.path(filepath)

    def retrieve_dataframe(self, value):
        """
        return the pandas DataFrame and add filepath as property to Dataframe
        """

        # read dataframe from storage
        absolute_filepath = self.get_absolute_path(value)
        dataframe = read_hdf(absolute_filepath)

        # add relative filepath as instance property for later use
        dataframe.filepath = self.get_relative_path(value)

        return dataframe

    def pre_save(self, model_instance, add):
        """
        save the dataframe field to an hdf5 field before saving the model
        """
        dataframe = super().pre_save(model_instance, add)

        if dataframe is None:
            return dataframe

        if not isinstance(dataframe, DataFrame):
            raise ValidationError(
                self.error_messages["invalid"], code="invalid",
            )

        self.save_dataframe_to_file(dataframe, model_instance)

        return dataframe

    def get_prep_value(self, value):
        """
        save the value of the dataframe.filepath set in pre_save
        """
        if value is None:
            return value

        # save only the filepath to the database
        if value.filepath:
            return value.filepath

    def save_dataframe_to_file(self, dataframe, model_instance):
        """
        write the Dataframe into an hdf5 file in storage at filepath
        """
        # try to retrieve the filepath set when loading from the database
        if not dataframe.get("filepath"):
            dataframe.filepath = self.generate_filepath(model_instance)

        full_filepath = self.storage.path(dataframe.filepath)

        # Create any intermediate directories that do not exist.
        directory = Path(full_filepath).parent

        if directory.exists() and not directory.is_dir():
            raise IOError(f"{directory} exists and is not a directory.")

        if not directory.is_dir():
            if self.storage.directory_permissions_mode is not None:
                directory.mkdir(
                    mode=self.storage.directory_permissions_mode,
                    parents=True,
                    exist_ok=True,
                )
            else:
                directory.mkdir(parents=True, exist_ok=True)

        # save to storage
        dataframe.to_hdf(full_filepath, "df", mode="w", format="fixed")

    def generate_filepath(self, instance):
        """
        return a filepath based on the model's class name, dataframe_field and unique fields
        """

        # create filename based on instance and field name
        # we do not want to end up with StravaRoute or SwitzerlandMobilityRoute
        if apps.get_model("routes", "Route") in getmro(instance.__class__):
            class_name = "Route"
        else:
            class_name = instance.__class__.__name__

        # generate unique id from unique fields:
        unique_id_values = []
        for field in self.unique_fields:
            unique_field_value = getattr(instance, field)

            # get field value or id if the field value is a related model instance
            unique_id_values.append(
                str(getattr(unique_field_value, "id", unique_field_value))
            )

        # filename, for example: route_data_<uuid>.h5
        filename = "{class_name}_{field_name}_{unique_id}.h5".format(
            class_name=class_name.lower(),
            field_name=self.name,
            unique_id="".join(unique_id_values),
        )

        # generate filepath
        dirname = self.upload_to
        filepath = Path(dirname, filename)
        return self.storage.generate_filename(filepath)


class NumpyArrayField(ArrayField):
    """
    Save NumPy arrays to PostgreSQl ArrayFields
    """

    def get_db_prep_value(self, value, connection, prepared=False):
        return super().get_db_prep_value(list(value), connection, prepared)

    def to_python(self, value):
        return super().to_python(array(value))

    def value_to_string(self, obj):
        return super().value_to_string(list(obj))


class CheckpointsSelectMultiple(CheckboxSelectMultiple):
    """
    Override the default CheckboxSelectMultiple Widget to serialize checkpoints
    as strings containing the place id and the line_location.
    """

    template_name = "forms/widgets/_checkpoints_multiple_input.html"

    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        # make sure it's a checkpoint
        Checkpoint = apps.get_model("routes", "checkpoint")
        if isinstance(value, Checkpoint):

            # add checkpoint place geojson as data-attribute to display on the map.
            attrs.update({"data-geom": value.place.get_geojson(fields=["name"])})

            # convert chekpoint to 'place_id' + "_" + 'line_location' string
            value = value.field_value

        return super().create_option(
            name, value, label, selected, index, subindex, attrs
        )


class CheckpointsChoiceField(MultipleChoiceField):
    """
    Custom form field to handle parsing and validation of
    checkpoints in the route form.
    """

    widget = CheckpointsSelectMultiple

    def to_python(self, value):
        """ Normalize data to a tuple (place.id, line_location)"""
        if not value:
            return []
        try:
            return [tuple(checkpoint_data.split("_")) for checkpoint_data in value]

        except KeyError:
            raise ValidationError(
                _("Invalid value: %(value)s"), code="invalid", params={"value": value},
            )

    def validate(self, value):
        """
        skip validation by the Parent class for now, as
        it seems to trigger an infinite loop..
        """
        # make sure we have two elements in the tuple
        for checkpoint in value:
            if len(checkpoint) != 2:
                raise ValidationError(
                    _("Invalid value: %(value)s"),
                    code="invalid",
                    params={"value": checkpoint},
                )

            # check that first half can be an int
            try:
                int(checkpoint[0])
            except ValueError:
                raise ValidationError(
                    _("Invalid value: %(value)s"),
                    code="invalid",
                    params={"value": checkpoint},
                )

            # check that second half is a float and
            # is not greater than 1.0
            try:
                if float(checkpoint[1]) > 1.0:
                    raise ValidationError(
                        _("Invalid value: %(value)s"),
                        code="invalid",
                        params={"value": checkpoint},
                    )

            except ValueError:
                raise ValidationError(
                    _("Invalid value: %(value)s"),
                    code="invalid",
                    params={"value": checkpoint},
                )
