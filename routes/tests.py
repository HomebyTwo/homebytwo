from django.test import TestCase
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse

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

        # Add user to the test database
        user = User.objects.create_user('testuser', 'test@test.com', 'test')

    def test_string_method(self):
        name = 'place_name'
        place = Place(name=name)
        self.assertTrue(name in str(place))

    def test_save_homebytwo_place_sets_source_id(self):
        place = Place(**self.data)
        place.save()
        self.assertEqual(place.data_source, 'homebytwo')
        self.assertEqual(place.source_id, str(place.id))

    # Views
    def test_importer_view_not_logged_redirected(self):
        url = reverse('importers')
        redirect_url = "/login/?next=" + url
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, redirect_url)

    def test_importer_view_logged_in(self):
        content = 'Import routes'
        url = reverse('importers')
        self.client.login(username='testuser', password='test')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(content in str(response.content))
