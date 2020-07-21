from django.db import IntegrityError, transaction
from django.forms import ChoiceField, Form, ModelChoiceField, ModelForm

from .fields import CheckpointsChoiceField
from .models import Activity, ActivityType, Checkpoint, Gear, Place, Route


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
                (checkpoint, str(checkpoint)) for checkpoint in checkpoints
            ]

            # set initial values the checkpoints already associated with the route
            self.initial["checkpoints"] = [
                checkpoint for checkpoint in checkpoints if checkpoint.id
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
                    for place_id, line_location in self.cleaned_data["checkpoints"]:
                        checkpoint, created = Checkpoint.objects.get_or_create(
                            route=model,
                            place=Place.objects.get(pk=place_id),
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
            "name",
            "activity_type",
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

    checkpoints = CheckpointsChoiceField(required=False)


class ActivityPerformanceForm(Form):
    """
    Choose the activity perfomance parameters to apply to the pace prediction.
    """

    activity_type_choices = [
        (value, label)
        for value, label in ActivityType.ACTIVITY_NAME_CHOICES
        if value in ActivityType.SUPPORTED_ACTIVITY_TYPES
    ]
    activity_type = ChoiceField(choices=activity_type_choices)

    def __init__(self, activity_performance=None, *args, **kwargs):
        """
        set choices of the form according to an ActivityPerformance object of the user.
        """
        super().__init__(*args, **kwargs)

        if activity_performance is None:
            return None

        # retrieve choices from the encoded categories in the prediction model
        gear_list = activity_performance.gear_categories
        workout_type_list = activity_performance.workout_type_categories

        # construct gear choices and configure choice field
        if gear_list != ["None"]:
            gears = Gear.objects.filter(strava_id__in=gear_list)
            gear_choices = [(gear.strava_id, gear.name) for gear in gears]

            # add None if necessary
            if "None" in gear_list:
                gear_choices.append(("None", "None"))

            self.fields["gear"] = ChoiceField(choices=gear_choices, required=False)

        # construct workout_type_choices and configure choice field
        # we use the display values because the one-hot encoder hates integers.
        if workout_type_list != ["None"]:
            workout_type_choices = [
                (choice_name, choice_name)
                for choice, choice_name in Activity.WORKOUT_TYPE_CHOICES
                if choice_name in workout_type_list
            ]

            self.fields["workout_type"] = ChoiceField(
                choices=workout_type_choices, required=False
            )
