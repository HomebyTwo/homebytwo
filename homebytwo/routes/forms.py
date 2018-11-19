from django.contrib.gis.db.models.functions import LineLocatePoint
from django.core.exceptions import ValidationError
from django.forms import (BooleanField, CheckboxSelectMultiple,
                          ModelChoiceField, ModelForm,
                          ModelMultipleChoiceField)

from .models import Place, Route, RoutePlace


class RouteForm(ModelForm):

    def __init__(self, *args, **kwargs):
        super(RouteForm, self).__init__(*args, **kwargs)

        if self.instance.geom:
            if 'end_place' in self.fields:
                start_place_qs = self.instance.get_closest_places_along_line(
                    line_location=0,  # start
                    max_distance=200,
                )
                self.fields['start_place'].queryset = start_place_qs

            if 'end_place' in self.fields:
                end_place_qs = self.instance.get_closest_places_along_line(
                    line_location=1,  # end
                    max_distance=200,
                )
                self.fields['end_place'].queryset = end_place_qs

            if 'places' in self.fields:
                places_qs = Place.objects.locate_places_on_line(
                    self.instance.geom,
                    max_distance=75,
                )

                self.fields['places'].queryset = places_qs

    start_place = ModelChoiceField(
        queryset=Place.objects.all(),
        empty_label=None,
        required=False,
    )

    end_place = ModelChoiceField(
        queryset=Place.objects.all(),
        empty_label=None,
        required=False,
    )

    places = ModelMultipleChoiceField(
        queryset=Place.objects.all(),
        widget=CheckboxSelectMultiple
    )

    class Meta:
        model = Route
        fields = [
            'image',
            'name',
            'activity_type',
            'description',
            'start_place',
            'places',
            'end_place',
        ]

    def save(self, commit=True):
        model = super(RouteForm, self).save(commit=False)
        if commit:
            model.save()

            places = self.cleaned_data['places']

            # save routeplaces in the form
            for place in places:
                line_location = LineLocatePoint(model.geom, place.geom)
                altitude_on_route = model.get_distance_data(
                    place.line_location,
                    'altitude',
                )

                RoutePlace.objects.get_or_create(
                    route=model,
                    place=place,
                    line_location=line_location,
                    altitude_on_route=altitude_on_route.m,
                )

            # delete places removed from the form
            for place in model.places.all():
                if place not in places:
                    RoutePlace.objects.get(place=place, route=model).delete()

        return model
