from django.db import IntegrityError, transaction
from django.forms import CheckboxSelectMultiple, ModelChoiceField, ModelForm

from .fields import CheckpointsChoiceField
from .models import Checkpoint, Place, Route


class RouteForm(ModelForm):
    """
    ModelForm used to import and edit routes.

    Does the heavy lifting of managing
    the 'start_place', 'end_place' and 'checkpoints' fields, all based the
    route geometry.

    """
    # override __init__ to provide initial data for the
    # 'start_place', 'end_place' and checkpoints field
    def __init__(self, *args, **kwargs):

        # parent class (ModelForm) __init__
        super().__init__(*args, **kwargs)

        # make sure the route has a linestring, because "start_place", "end_place"
        # and "checkpoints" are based on it.
        if self.instance.geom:
            self.fields["start_place"].queryset = self.instance.get_start_places()
            self.fields["end_place"].queryset = self.instance.get_end_places()

            # retrieve checkpoints within range of the route
            checkpoints = self.instance.find_possible_checkpoints()

            # set choices to all possible checkpoints
            self.fields["checkpoints"].choices = [
                (checkpoint.field_value, str(checkpoint))
                for checkpoint in checkpoints
            ]

            # set initial values the checkpoints already associated with the route
            self.initial["checkpoints"] = [
                checkpoint.field_value
                for checkpoint in checkpoints
                if checkpoint.id
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
                    checkpoints_to_delete = set(old_checkpoints) - set(
                        checkpoints_saved
                    )
                    for checkpoint in checkpoints_to_delete:
                        checkpoint.delete()

            except IntegrityError:
                raise

        return model

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

    start_place = ModelChoiceField(
        queryset=Place.objects.all(), empty_label=None, required=False,
    )

    end_place = ModelChoiceField(
        queryset=Place.objects.all(), empty_label=None, required=False,
    )

    checkpoints = CheckpointsChoiceField(
        widget=CheckboxSelectMultiple,
        required=False,
    )
