from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils.six import StringIO

from ..models import Swissname3dPlace
from routes.models import Place

import os


def get_path_to_data(file_type='shp'):
    dir_path = os.path.dirname(os.path.realpath(__file__))

    if file_type == 'shp':
        # Test file with 35 features only
        shapefile = os.path.join(dir_path, 'data', 'TestSwissNAMES3D_PKT.shp')
        return shapefile

    else:
        # Bad empty data
        text_data = os.path.join(dir_path, 'data', 'text.txt')
        return text_data


def get_place_data(data_source='swissname3d'):
    data = {
        'swissname3d': {
            'place_type': 'Gipfel',
            'name': 'Place3D_name',
            'description': 'Place3D_description',
            'altitude': 666,
            'public_transport': False,
            'source_id': '1',
            'geom': 'POINT(0 0)',
        },

        'homebytwo': {
            'place_type': 'Church',
            'name': 'Other_Name',
            'description': 'Other_description',
            'altitude': 1000,
            'public_transport': True,
            'geom': 'POINT(0 0)',
        },
    }

    return data[data_source]


# Models
class Swissname3dModelTest(TestCase):

    def test_create_instance(self):
        place3d = Swissname3dPlace(**get_place_data())
        self.assertEqual('Place3D_name', str(place3d))

    def test_save_instance(self):
        place3d = Swissname3dPlace(**get_place_data())
        place3d.save()
        self.assertEqual(Swissname3dPlace.objects.count(), 1)

    def test_separate_from_other_place_models(self):
        place3d = Swissname3dPlace(**get_place_data())
        place3d.save()
        other_place = Place(**get_place_data('homebytwo'))
        other_place.save()
        self.assertEqual(Swissname3dPlace.objects.count(), 1)
        self.assertEqual(Place.objects.count(), 2)

    def test_prevent_duplicate_entries(self):
        place3d_1 = Swissname3dPlace(**get_place_data())
        place3d_1.save()

        place3d_2 = Swissname3dPlace(**get_place_data())
        place3d_2.name = 'Other_3D_place'
        place3d_2.save()
        self.assertEqual(Place.objects.count(), 1)

        place3d_3 = Swissname3dPlace(**get_place_data())
        place3d_3.source_id = '2'
        place3d_3.save()
        self.assertEqual(Place.objects.count(), 2)


# Management Commands
class Importswissname3dTest(TestCase):

    def test_command_output_inexistant_file(self):
        with self.assertRaises(OSError):
            call_command('importswissname3d', 'toto')

    def test_command_output_incorrect_shapefile(self):
        with self.assertRaises(CommandError):
            call_command('importswissname3d', get_path_to_data('bad'))

    def test_command_output_correct_shapefile(self):
        out = StringIO()
        call_command('importswissname3d', get_path_to_data('shp'),
                     '--no-input', stdout=out)
        self.assertTrue('Successfully imported' in out.getvalue())

    def test_command_limit_option(self):
        out = StringIO()
        call_command('importswissname3d', '--limit', '10',
                     '--no-input', get_path_to_data('shp'), stdout=out)
        self.assertTrue('Successfully imported 10 places' in out.getvalue())
        self.assertEqual(Swissname3dPlace.objects.count(), 10)

    def test_command_limit_higher_than_feature_count(self):
        out = StringIO()
        call_command('importswissname3d', '--limit', '100',
                     '--no-input', get_path_to_data('shp'), stdout=out)
        self.assertTrue('Successfully imported 35 places' in out.getvalue())
        self.assertEqual(Swissname3dPlace.objects.count(), 35)

    def test_command_limit_delete_replace_option(self):
        out = StringIO()
        call_command('importswissname3d', '--limit', '10',
                     '--no-input', get_path_to_data('shp'), stdout=out)
        call_command('importswissname3d', '--delete',
                     '--no-input', get_path_to_data('shp'), stdout=out)
        self.assertIn('Successfully deleted 10 places.', out.getvalue())
        self.assertIn('Successfully imported 35 places.', out.getvalue())
        self.assertEqual(Swissname3dPlace.objects.count(), 35)

    def test_command_delete_swissname3d_only(self):
        out = StringIO()
        place3d = Swissname3dPlace(**get_place_data())
        place3d.save()
        place = Place(**get_place_data('homebytwo'))
        place.save()
        self.assertEqual(Place.objects.count(), 2)  # 1 + 1
        self.assertEqual(Swissname3dPlace.objects.count(), 1)
        call_command('importswissname3d', '--delete',
                     '--no-input', get_path_to_data('shp'), stdout=out)
        self.assertEqual(Place.objects.count(), 36)  # 35 + 1
        self.assertEqual(Swissname3dPlace.objects.count(), 35)
