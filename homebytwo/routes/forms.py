from django import forms
from .models import Route, Place, RoutePlace


class RouteForm(forms.ModelForm):

    class PlaceChoiceField(forms.ModelChoiceField):
        def label_from_instance(self, obj):
            return '%s - %s, %d meters away.' % (
                obj.name,
                obj.get_place_type_display(),
            )

    start_place = PlaceChoiceField(
        queryset=Place.objects.all(),
        empty_label=None,
        required=False,
    )

    end_place = PlaceChoiceField(
        queryset=Place.objects.all(),
        empty_label=None,
        required=False,
    )

    class Meta:
        model = Route
        fields = [
            'source_id',
            'name',
            'totalup',
            'totaldown',
            'length',
            'geom',
            'start_place',
            'end_place',
            'data',
            'activity_type',
        ]


class RoutePlaceForm(forms.ModelForm):
    class Meta:
        model = RoutePlace
        fields = ['place', 'line_location', 'altitude_on_route', 'include']

    include = forms.BooleanField(
        required=False,
        initial=True,
    )