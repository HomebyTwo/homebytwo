
from django.forms import CheckboxSelectMultiple

from django_filters import FilterSet, MultipleChoiceFilter

from ..routes.models import Place


class PlaceFilter(FilterSet):
    place_type = MultipleChoiceFilter(
        choices=Place.PLACE_TYPE_CHOICES,
        widget=CheckboxSelectMultiple,
    )

    class Meta:
        model = Place
        fields = []
