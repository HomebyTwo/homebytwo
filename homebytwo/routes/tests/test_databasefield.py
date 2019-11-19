from os.path import exists, join

from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import TestCase

import numpy as np
from pandas import DataFrame

from ..fields import DataFrameField, DataFrameFormField
from .factories import RouteFactory


class DataFrameFieldTestCase(TestCase):
    def test_model_field_get_prep_value(self):
        data = DataFrame(np.random.randn(10, 2))
        field = DataFrameField(max_length=100, save_to="test")
        filename = field.get_prep_value(data)
        fullpath = join(
            settings.BASE_DIR, settings.MEDIA_ROOT, field.save_to, filename,
        )

        self.assertEqual(len(filename), 35)  # = 32 + '.h5'
        self.assertTrue(exists(fullpath))
        self.assertTrue((data == field.to_python(filename)).all().all())

        test_str = "coucou!"
        field = DataFrameField(max_length=100, save_to="test")
        with self.assertRaises(ValidationError):
            field.get_prep_value(test_str)

    def test_model_field_to_python(self):
        field = DataFrameField(max_length=100, save_to="test")

        random_data = DataFrame(np.random.randn(10, 2))
        filename = field.get_prep_value(random_data)

        data = field.to_python(filename)
        self.assertTrue((random_data == data).all().all())
        self.assertTrue(hasattr(data, "filename"))

        data = field.to_python(random_data)
        self.assertTrue((random_data == data).all().all())

        data = field.to_python(None)
        self.assertEqual(data, None)

        data = field.to_python("")
        self.assertEqual(data, None)

    def test_form_field_prepare_value(self):
        form_field = DataFrameFormField()
        value = DataFrame([["a", "b"], ["c", "d"]], columns=["col 1", "col 2"])

        json = form_field.prepare_value(value)
        self.assertTrue((value == form_field.to_python(json)).all().all())
        self.assertTrue(isinstance(json, str))

        value = None
        json = form_field.prepare_value(None)
        self.assertEqual(value, form_field.to_python(json))
        self.assertTrue(isinstance(json, str))
        self.assertEqual(json, "")

        value = DataFrame()
        json = form_field.prepare_value(value)
        self.assertTrue((value == form_field.to_python(json)).all().all())

    def test_form_field_has_changed(self):
        form_field = DataFrameFormField()

        initial = DataFrame([["a", "b"], ["c", "d"]], columns=["col 1", "col 2"])

        empty_data = None
        self.assertTrue(form_field.has_changed(initial, empty_data))
        self.assertFalse(form_field.has_changed(empty_data, empty_data))

        same_data = initial
        self.assertFalse(form_field.has_changed(initial, same_data))

        partly_changed_data = DataFrame(
            [["a", "b"], ["c", "f"]], columns=["col 1", "col 2"]
        )
        self.assertTrue(form_field.has_changed(initial, partly_changed_data))

        different_shape_data = partly_changed_data = DataFrame(
            [["a", "b", "c"], ["c", "f", "g"], ["c", "f", "h"]],
            columns=["col 1", "col 2", "col 3"],
        )
        self.assertTrue(form_field.has_changed(initial, different_shape_data))

        changed_data = DataFrame([["e", "f"], ["g", "h"]], columns=["col 1", "col 2"])
        self.assertTrue(form_field.has_changed(initial, changed_data))

    def test_form_field_to_python(self):
        form_field = DataFrameFormField()

        route = RouteFactory()
        route_value = route.data.to_json(orient="records")
        self.assertFalse(form_field.to_python(route_value).empty)
        self.assertTrue(isinstance(form_field.to_python(route_value), DataFrame))

        empty_df = DataFrame().to_json(orient="records")
        self.assertTrue(form_field.to_python(empty_df).empty)

        self.assertEqual(form_field.to_python(""), None)
