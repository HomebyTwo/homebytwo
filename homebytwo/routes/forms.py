from django.db import IntegrityError, transaction
from django.forms import ChoiceField, Form, ModelChoiceField, ModelForm

from .fields import CheckpointsChoiceField
from .models import (
    Activity,
    ActivityPerformance,
    ActivityType,
    Checkpoint,
    Gear,
    Place,
    Route,
)


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

    The form contains at least one field (activity_type) and at most three:
    the gear and workout_type fields are displayed if the athlete's performance profile
    contains such options, e.g. Run or Ride.
    """

    def __init__(self, route, athlete=None, *args, **kwargs):
        """
        set field choices according to the route's activity type and the athlete's ActivityPerformance objects.
        """
        super().__init__(*args, **kwargs)

        if self.is_bound:
            try:
                # do not get or create because the data is not cleaned
                route.activity_type = ActivityType.objects.get(
                    name=self.data["activity_type"]
                )
            except ActivityType.DoesNotExist:
                pass

        # get generic activity type choices based on supported activities
        activity_type_choices = [
            (value, label)
            for value, label in ActivityType.ACTIVITY_NAME_CHOICES
            if value in ActivityType.SUPPORTED_ACTIVITY_TYPES
        ]

        if athlete:
            # retrieve activity types for which the athlete has a prediction model.
            athlete_activity_types = athlete.activityperformance_set.all()
            athlete_activity_type_list = athlete_activity_types.values_list(
                "activity_type__name", flat=True
            )

            # try to get the athlete's prediction model for the route's activity type
            try:
                activity_performance = athlete_activity_types.get(
                    activity_type=route.activity_type
                )

            except ActivityPerformance.DoesNotExist:
                activity_performance = None
                help_text = "You have no prediction model for this activity type."

            else:
                # limit activity type choices to athlete's existing prediction models
                activity_type_choices = [
                    (value, label)
                    for value, label in activity_type_choices
                    if value in athlete_activity_type_list
                ]
                # inform on the prediction model's reliability
                help_text = "Your prediction score for this activity type is: {score:.1%}".format(
                    score=activity_performance.model_score
                )

        else:
            help_text = "Log-in or sign-up to see your personalized schedule."

        self.fields["activity_type"] = ChoiceField(
            choices=activity_type_choices, help_text=help_text
        )

        # only try to create gear_list and workout_type fields
        # for athletes with a prediction model for the route activity type
        if not athlete or not activity_performance:
            return

        # retrieve gear and workout type choices from the categories in the prediction model
        gear_list = activity_performance.gear_categories
        workout_type_list = activity_performance.workout_type_categories

        # construct gear choices and configure choice field
        if not all(gear_list == ["None"]):
            gears = Gear.objects.filter(strava_id__in=gear_list)
            gear_choices = [(gear.strava_id, gear.name) for gear in gears]

            # add None if necessary
            if "None" in gear_list:
                gear_choices.append(("None", "None"))

            self.fields["gear"] = ChoiceField(choices=gear_choices, required=False)

        # construct workout_type_choices and configure choice field
        # we use the display values because the one-hot encoder hates integers.
        if not all(workout_type_list == ["None"]):
            workout_type_choices = [
                (choice_name, choice_name)
                for choice, choice_name in Activity.WORKOUT_TYPE_CHOICES
                if choice_name in workout_type_list
            ]

            self.fields["workout_type"] = ChoiceField(
                choices=workout_type_choices, required=False
            )
