from django.test import TestCase
from .models import Place

from datetime import datetime

# Create your tests here.


class PlaceTestCase(TestCase):
    def test_non_public_transport_place_raise_exception(self):
        no_public_transport = Place.objects.filter(public_transport=False).first()
        time = datetime.now()
        no_public_transport.get_timetable_info(time, 'Lausanne')
