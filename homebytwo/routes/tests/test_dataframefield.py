import os
import shutil
import stat
from tempfile import TemporaryDirectory

from django.core.checks import Error
from django.core.exceptions import SuspiciousFileOperation, ValidationError
from django.db import connection
from django.test import TestCase, override_settings

from ...utils.factories import AthleteFactory
from ..fields import DataFrameField
from ..models import Route
from .factories import RouteFactory


class DataFrameFieldTestCase(TestCase):
    def test_dataframe_field_deconstruct_reconstruct(self):
        field_instance = DataFrameField(upload_to="foo", storage="bar", max_length=80)
        name, path, args, kwargs = field_instance.deconstruct()
        new_instance = DataFrameField(*args, **kwargs)
        self.assertEqual(field_instance.upload_to, new_instance.upload_to)
        self.assertEqual(field_instance.storage, new_instance.storage)
        self.assertEqual(field_instance.max_length, new_instance.max_length)

    def test_dataframe_field_init(self):
        field_instance = DataFrameField(
            upload_to="foo", storage="bar", max_length=100, unique_fields=["fooba"]
        )

        assert field_instance.upload_to == "foo"
        assert field_instance.storage == "bar"
        assert field_instance.max_length == 100

    def test_dataframe_field_check_no_unique_fields(self):
        field = DataFrameField(
            upload_to="foo", storage="bar", max_length=80, unique_fields=[],
        )
        field.name = "data"
        field.model = Route

        errors = field.check()
        expected_errors = [
            Error(
                "you must provide a list of unique fields.",
                obj=field,
                id="homebytwo.E001",
            )
        ]
        assert errors == expected_errors

    def test_dataframe_field_check_inexistant_unique_field(self):
        field = DataFrameField(
            upload_to="foo", storage="bar", max_length=80, unique_fields=["foo"],
        )
        field.name = "data"
        field.model = Route

        errors = field.check()
        error = "Route has no field named 'foo'"
        expected_errors = [
            Error(
                "unique_fields is badly set: {}".format(error),
                obj=field,
                id="homebytwo.E002",
            )
        ]
        assert errors == expected_errors

    def test_dataframe_field_check_ok(self):
        field = DataFrameField(
            upload_to="foo", storage="bar", max_length=80, unique_fields=["data"],
        )
        field.name = "data"
        field.model = Route
        errors = field.check()
        expected_errors = []

        assert errors == expected_errors

    def test_dataframe_from_db_value_None(self):
        route = RouteFactory(data=None)
        route.refresh_from_db()
        assert route.data is None

    def test_dataframe_from_db_value_no_dirname(self):
        route = RouteFactory()
        complete_filepath = route.data.filepath

        # save DB entry without dirname
        dirname, filename = os.path.split(route.data.filepath)
        query = "UPDATE routes_route SET data='{}' WHERE id={}".format(
            filename, route.id
        )
        with connection.cursor() as cursor:
            cursor.execute(query)

        route.refresh_from_db()
        assert route.data.filepath == complete_filepath

    def test_dataframe_from_db_value_missing_file(self):
        route = RouteFactory()

        query = "UPDATE routes_route SET data='{}' WHERE id={}".format(
            "inexistant.h5", route.id
        )
        with connection.cursor() as cursor:
            cursor.execute(query)

        with self.assertRaises(IOError):
            route.refresh_from_db()

    def test_dataframe_from_db_value_leading_slash(self):
        route = RouteFactory()

        # save DB entry with a leading slash
        dirname, filename = os.path.split(route.data.filepath)
        query = "UPDATE routes_route SET data='/{}' WHERE id={}".format(
            filename, route.id
        )
        with connection.cursor() as cursor:
            cursor.execute(query)

        with self.assertRaises(SuspiciousFileOperation):
            route.refresh_from_db()

    def test_dataframe_from_db_value_not_hdf5(self):
        route = RouteFactory()
        field = DataFrameField()
        fullpath = field.storage.path(route.data.filepath)

        os.remove(fullpath)

        with open(fullpath, "w+") as file:
            file.write("I will not buy this record, it is scratched!")

        with self.assertRaises(OSError):
            route.refresh_from_db()

    def test_dataframe_pre_save_not_a_dataframe(self):
        route = RouteFactory()
        route.data = "The plumage doesn't enter into it, it's not a dataframe!"
        with self.assertRaises(ValidationError):
            route.save()

    @override_settings(
        MEDIA_ROOT=TemporaryDirectory().name, FILE_UPLOAD_DIRECTORY_PERMISSIONS=0o751
    )
    def test_dataframe_save_dataframe_to_file_directory_permissions(self):

        route = RouteFactory()
        field = route._meta.get_field("data")
        dirname, filename = os.path.split(field.get_absolute_path(route.data.filepath))
        mode = os.stat(dirname).st_mode
        assert stat.filemode(mode) == "drwxr-x--x"

    def test_dataframe_save_dataframe_to_file_exists_not_a_directory(self):
        route = RouteFactory()
        field = route._meta.get_field("data")
        filepath = field.get_absolute_path(route.data.filepath)
        dirname, filename = os.path.split(filepath)
        shutil.rmtree(dirname)
        with open(dirname, "w+") as file:
            file.write("I cannot wait until lunchtime!")
        with self.assertRaises(IOError):
            route.save(update_fields=["data"])
        os.remove(dirname)

    def test_dataframe_save_dataframe_to_file_lost_filepath(self):
        route = RouteFactory()
        filepath = route.data.filepath
        del route.data.filepath
        route.save()

        self.assertEqual(route.data.filepath, filepath)

    def test_dataframe_save_dataframe_to_file_new_object(self):
        athlete = AthleteFactory()
        uuid = 0x12345678123412341234123456789ABC

        route = RouteFactory(
            start_place=None, end_place=None, athlete=athlete, uuid=uuid
        )

        filepath = "{}/{}_{}_{}.h5".format(
            "data", route.__class__.__name__.lower(), "data", uuid
        )

        route.save()

        self.assertEqual(route.data.filepath, filepath)
