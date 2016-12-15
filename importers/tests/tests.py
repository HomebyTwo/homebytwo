from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils.six import StringIO

import os


# Management Commands
class Importswissname3dTest(TestCase):

    dir_path = os.path.dirname(os.path.realpath(__file__))
    text_data = os.path.join(dir_path, 'data', 'text.txt')

    # Test file with 56 features only
    shapefile = os.path.join(dir_path, 'data', 'MinSwissNAMES3D_PKT.shp')

    def test_command_output_inexistant_file(self):
        with self.assertRaises(FileNotFoundError):
            call_command('importswissname3d', 'toto')

    def test_command_output_incorrect_shapefile(self):
        with self.assertRaises(CommandError):
            call_command('importswissname3d', self.text_data)

    def test_command_output_correct_shapefile(self):
        out = StringIO()
        call_command('importswissname3d', self.shapefile, stdout=out)
        self.assertIn('Successfully imported', out.getvalue())

    def test_command_limit_option(self):
        out = StringIO()
        call_command('importswissname3d', '--limit', '10', self.shapefile, stdout=out)
        self.assertIn('Successfully imported 10 places', out.getvalue())

    def test_command_limit_higher_than_feature_count(self):
        out = StringIO()
        call_command('importswissname3d', '--limit', '100', self.shapefile, stdout=out)
        self.assertIn('Successfully imported 56 places', out.getvalue())
