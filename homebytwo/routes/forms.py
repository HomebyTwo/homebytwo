from django.db import transaction
from django.db.models import Count
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
    def __init__(self, update=False, *args, **kwargs):

        # parent class (ModelForm) __init__
        super().__init__(*args, **kwargs)
        self.fields["activity_type"].queryset = ActivityType.objects.for_athlete(self.instance.athlete)

        # make sure the route has a linestring, because "start_place", "end_place"
        # and "checkpoints" are based on it.
        if self.instance.geom:
            self.fields["start_place"].queryset = self.instance.get_start_places()
            self.fields["end_place"].queryset = self.instance.get_end_places()

            # retrieve checkpoints within range of the route
            checkpoints = self.instance.find_possible_checkpoints(updated_geom=update)

            # set choices to all possible checkpoints
            self.fields["checkpoints"].choices = [
                (checkpoint, str(checkpoint)) for checkpoint in checkpoints
            ]
            if update:
                # select places that are among the existing checkpoints
                self.initial["checkpoints"] = [
                    checkpoint
                    for checkpoint in checkpoints
                    # new checkpoint place is among places in the former checkpoints
                    if self.instance.checkpoint_set.filter(
                        place=checkpoint.place
                    ).exists()
                ]
            else:
                # select checkpoints already associated with the route
                self.initial["checkpoints"] = list(filter(lambda o: o.id, checkpoints))

    def save(self, commit=True):
        model = super().save(commit=False)

        # checkpoints associated with the route in the database
        old_checkpoints = model.checkpoint_set.all()

        if commit:
            with transaction.atomic():
                try:
                    # calculate permanent data columns
                    model.update_permanent_track_data(
                        min_step_distance=1, max_gradient=100, commit=False
                    )
                except ValueError as error:
                    message = f"Route cannot be imported: {error}."
                    self.add_error(None, message)
                    return

                model.update_track_details_from_data(commit=False)
                model.save()

                # save form checkpoints
                checkpoints_saved = []
                for place_id, line_location in self.cleaned_data["checkpoints"]:
                    checkpoint, created = Checkpoint.objects.get_or_create(
                        route=model,
                        place=Place.objects.get(pk=place_id),
                        line_location=line_location,
                    )
                    checkpoints_saved.append(checkpoint)

                # delete places that were removed from the form
                saved_ids = [checkpoint.id for checkpoint in checkpoints_saved]
                old_checkpoints.exclude(pk__in=saved_ids).delete()

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
        queryset=Place.objects.all(),
        empty_label=None,
        required=False,
    )

    end_place = ModelChoiceField(
        queryset=Place.objects.all(),
        empty_label=None,
        required=False,
    )

    checkpoints = CheckpointsChoiceField(required=False)


class ActivityPerformanceForm(Form):
    """
    Choose the activity performance parameters to apply to the pace prediction.

    The form contains at least one field (activity_type) and at most three:
    the gear and workout_type fields are displayed if the athlete's performance profile
    contains such options, e.g. Run or Ride.
    """

    def __init__(self, route, athlete=None, *args, **kwargs):
        """
        set field choices according to the route's activity type and the athlete's
        ActivityPerformance objects.
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

        # get activity types available for prediction
        activity_types = ActivityType.objects.predicted()
        prediction_model = route.activity_type

        if athlete:
            # filter activity types for the athlete
            activity_types = activity_types.filter(performances__athlete=athlete)

            # try to get the athlete's prediction model for the route's activity type
            try:
                prediction_model = route.activity_type.performances.get(athlete=athlete)
                help_text = "Prediction score: {score:.1%}".format(
                    score=prediction_model.model_score
                )

            except ActivityPerformance.DoesNotExist:
                help_text = (
                    "You have no prediction model for this route's activity type."
                )

        else:
            help_text = (
                "Using data from homebytwo athlete data for predictions. "
                "Log-in or sign-up to see your personalized schedule."
            )

        # construct activity_type choices
        activity_type_choices = [
            (activity_type.name, activity_type.get_name_display())
            for activity_type in activity_types
        ]
        self.fields["activity_type"] = ChoiceField(
            choices=activity_type_choices, help_text=help_text
        )

        # construct gear choices and configure choice field
        gear_list = getattr(prediction_model, "gear_categories", None)
        if gear_list is not None and not all(gear_list == ["None"]):
            gears = Gear.objects.filter(strava_id__in=gear_list)
            gears = gears.order_by("name")
            gear_choices = [(gear.strava_id, gear.name) for gear in gears]

            # add None if necessary
            if "None" in gear_list:
                gear_choices.append(("None", "None"))

            self.fields["gear"] = ChoiceField(choices=gear_choices, required=False)

        # construct workout_type_choices and configure choice field
        # we use the display values because the one-hot encoder hates integers.
        workout_type_list = getattr(prediction_model, "workout_type_categories", None)
        if workout_type_list is not None and not all(workout_type_list == ["None"]):
            workout_type_choices = [
                (choice_name, choice_name)
                for choice, choice_name in Activity.WORKOUT_TYPE_CHOICES
                if choice_name in workout_type_list
            ]

            self.fields["workout_type"] = ChoiceField(
                choices=workout_type_choices, required=False
            )
