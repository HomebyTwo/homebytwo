from django.db import IntegrityError, transaction
from django.forms import (
    CheckboxSelectMultiple,
    ModelChoiceField,
    ModelForm,
    MultipleChoiceField,
    ValidationError,
)
from django.utils.translation import gettext as _

from .models import Checkpoint, Place, Route


class RouteForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.geom:
            if "start_place" in self.fields:
                self.fields["start_place"].queryset = self.instance.get_start_places()

            if "end_place" in self.fields:
                self.fields["end_place"].queryset = self.instance.get_end_places()

            if "checkpoints" in self.fields:
                checkpoints = self.instance.find_possible_checkpoints()

                # set available choices to the list of all possible checkpoints
                self.fields["checkpoints"].choices = [
                    (checkpoint.field_value, str(checkpoint))
                    for checkpoint in checkpoints
                ]

                # checkpoints that are already associated with the route
                self.initial["checkpoints"] = [
                    checkpoint.field_value
                    for checkpoint in checkpoints
                    if checkpoint.id
                ]

    def clean_checkpoints(self):
        checkpoints = self.cleaned_data["checkpoints"]
        return checkpoints

    start_place = ModelChoiceField(
        queryset=Place.objects.all(), empty_label=None, required=False,
    )

    end_place = ModelChoiceField(
        queryset=Place.objects.all(), empty_label=None, required=False,
    )

    class CheckpointsChoiceField(MultipleChoiceField):
        def to_python(self, value):
            """ Normalize data to a tuple (place.id, line_location)"""
            if value:
                try:
                    value = [tuple(checkpoint_data.split("_")) for checkpoint_data in value]
                except KeyError:
                    raise ValidationError(
                        _("Invalid value: %(value)s"),
                        code="invalid",
                        params={"value": value},
                    )

                return value

        def validate(self, value):
            # Validate
            if value not in [None, []]:
                for checkpoint in value:
                    if len(checkpoint) != 2:
                        raise ValidationError(
                            _("Invalid value: %(value)s"),
                            code="invalid",
                            params={"value": checkpoint},
                        )

    checkpoints = CheckpointsChoiceField(widget=CheckboxSelectMultiple, required=False,)

    class Meta:
        model = Route
        fields = [
            "image",
            "name",
            "activity_type",
            "description",
            "start_place",
            "checkpoints",
            "end_place",
        ]

    def save(self, commit=True):
        model = super().save(commit=False)

        # checkpoints associated with the route in the database
        checkpoints_saved = []
        old_checkpoints = model.checkpoint_set.all()

        if commit:
            try:
                with transaction.atomic():
                    model.save()

                    # save form checkpoints
                    for place, line_location in self.cleaned_data["checkpoints"]:
                        checkpoint, created = Checkpoint.objects.get_or_create(
                            route=model,
                            place=Place.objects.get(pk=place),
                            line_location=line_location,
                        )

                        checkpoints_saved.append(checkpoint)

                    # delete places removed from the form
                    checkpoints_to_delete = set(old_checkpoints) - set(checkpoints_saved)
                    for checkpoint in checkpoints_to_delete:
                        checkpoint.delete()

            except IntegrityError:
                raise

        return model
