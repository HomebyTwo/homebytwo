from django.test import TestCase

from .models import Place


class PlaceTestCase(TestCase):

    def setUp(self):
        self.data = {
            'place_type': 'Church',
            'name': 'Place_Name',
            'description': 'Place_description',
            'altitude': 1000,
            'public_transport': True,
            'geom': 'POINT(0 0)',
        }

    def test_string_method(self):
        name = 'place_name'
        place = Place(name=name)
        self.assertTrue(name in str(place))

    def test_save_homebytwo_place_sets_source_id(self):
        place = Place(**self.data)
        place.save()
        self.assertEqual(place.data_source, 'homebytwo')
        self.assertEqual(place.source_id, str(place.id))
