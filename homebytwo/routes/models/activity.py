from django.contrib.gis.db import models
from django.contrib.gis.measure import D

from numpy import array
from pandas import DataFrame
from stravalib import unithelper
from stravalib.exc import ObjectNotFound

from ...core.models import TimeStampedModel
from ..fields import DataFrameField, NumpyArrayField
from ..prediction_model import PredictionModel


def get_default_array():
    """
    default array (mutable) for the `regression_coefficients` NumpyArrayField.
    """
    return array([0.0, 0.0, 0.0, 0.075, 0.0004, 0.0001, 0.0001]).copy()


def get_default_category():
    """
    default list (mutable) for the categories saved by the one-hot encoder ArrayField.
    """
    return array(["None"]).copy()


class ActivityQuerySet(models.QuerySet):
    def for_user(self, user):
        """
        return all routes of a given user.
        this is convenient with the 'request.user' object in views.
        """
        return self.filter(athlete=user.athlete)


class ActivityManager(models.Manager):
    def get_queryset(self):
        return ActivityQuerySet(self.model, using=self._db)

    def for_user(self, user):
        return self.get_queryset().for_user(user)

    def update_user_activities_from_strava(
        self, athlete, after=None, before=None, limit=0
    ):
        """
        fetches an athlete's activities from Strava and saves them to the Database.
        It erases the ones that are no more available because they have been deleted
        or set to private. It returns all of the athlete's current activities.

        Parameters:
        'after': start date is after specified value (UTC). datetime.datetime, str or None.
        'before': start date is before specified value (UTC). datetime.datetime or str or None
        'limit': maximum activites retrieved. Integer

        See https://pythonhosted.org/stravalib/usage/activities.html#list-of-activities
        and https://developers.strava.com/playground/#/Activities/getLoggedInAthleteActivities
        """

        # retrieve the athlete's activities on Strava
        strava_activities = athlete.strava_client.get_activities(
            before=before, after=after, limit=limit
        )

        # create or update retrieved activities
        activities = []
        for strava_activity in strava_activities:
            if strava_activity.type not in ActivityType.SUPPORTED_ACTIVITY_TYPES:
                continue
            try:
                activity = Activity.objects.get(strava_id=strava_activity.id)

            except Activity.DoesNotExist:
                activity = Activity(athlete=athlete, strava_id=strava_activity.id)

            activity.save_from_strava(strava_activity)
            activities.append(activity)

        # delete activities not in the Strava result
        existing_activities = Activity.objects.filter(athlete=athlete)
        existing_activities.exclude(
            id__in=[activity.id for activity in activities]
        ).delete()

        return activities


class Activity(TimeStampedModel):
    """
    All activities published by the athletes on Strava.
    User activities used to calculate performance by activity type.
    """

    NONE = None
    DEFAULT_RUN = 0
    RACE_RUN = 1
    LONG_RUN = 2
    WORKOUT_RUN = 3
    DEFAULT_RIDE = 10
    RACE_RIDE = 11
    WORKOUT_RIDE = 12

    WORKOUT_TYPE_CHOICES = [
        (NONE, "None"),
        (DEFAULT_RUN, "default run"),
        (RACE_RUN, "race run"),
        (LONG_RUN, "long run"),
        (WORKOUT_RUN, "workout run"),
        (DEFAULT_RIDE, "default ride"),
        (RACE_RIDE, "race ride"),
        (WORKOUT_RIDE, "workout ride"),
    ]

    # name of the activity as imported from Strava
    name = models.CharField(max_length=255)

    # description of the activity as imported from Strava
    description = models.TextField(blank=True)

    # Activity ID on Strava
    strava_id = models.BigIntegerField(unique=True)

    # Starting date and time of the activity in UTC
    start_date = models.DateTimeField()

    # Athlete whose activities have been imported from Strava
    athlete = models.ForeignKey(
        "Athlete", on_delete=models.CASCADE, related_name="activities"
    )

    # Athlete whose activities have been imported from Strava
    activity_type = models.ForeignKey(
        "ActivityType", on_delete=models.PROTECT, related_name="activities"
    )

    # Was the activity created manually? If yes there are no associated data streams.
    manual = models.BooleanField(default=False)

    # Total activity distance
    distance = models.FloatField("Activity distance in m", blank=True, null=True)

    # elevation gain in m
    total_elevation_gain = models.FloatField(
        "Total elevation gain in m", blank=True, null=True
    )

    # total duration of the activity in seconds as opposed to moving time
    elapsed_time = models.DurationField(
        "Total activity time as timedelta", blank=True, null=True
    )

    # time in movement during the activity
    moving_time = models.DurationField(
        "Movement time as timedelta", blank=True, null=True
    )

    # streams retrieved from the Strava API
    streams = DataFrameField(
        null=True, upload_to="streams", unique_fields=["strava_id"]
    )

    # Workout Type as defined in Strava
    workout_type = models.SmallIntegerField(
        choices=WORKOUT_TYPE_CHOICES, blank=True, null=True
    )

    # is the activity flagged as a commute?
    commute = models.BooleanField(default=False)

    # Gear used if any
    gear = models.ForeignKey(
        "Gear",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="activities",
    )

    class Meta:
        ordering = ["-start_date"]
        verbose_name_plural = "activities"

    # Custom manager
    objects = ActivityManager()

    def __str__(self):
        return "{0}: {1} - {2}".format(self.activity_type, self.name, self.athlete)

    def get_strava_url(self):
        # return the absolute URL to the activity on Strava
        return "https://www.strava.com/activities/{}".format(self.strava_id)

    def get_distance(self):
        # return the activity distance as a Distance object
        return D(m=self.distance)

    def get_total_elevation_gain(self):
        # return the activity distance as a Distance object
        return D(m=self.total_elevation_gain)

    def update_from_strava(self):
        # retrieve activity from Strava and update it.
        try:
            strava_activity = self.athlete.strava_client.get_activity(self.strava_id)

        # Object not found on Strava: e.g. changed privacy setting
        except ObjectNotFound:
            self.delete()

        # strava activity was found in Strava
        else:
            self.save_from_strava(strava_activity)

    def save_from_strava(self, strava_activity):
        """
        create or update an activity based on information received from Strava.

        `strava_activity` is the activity object returned by the Strava API client.
        returns the saved activity.
        """

        # fields from the Strava API object mapped to the Activity Model
        fields_map = {
            "name": strava_activity.name,
            "activity_type": strava_activity.type,
            "manual": strava_activity.manual,
            "start_date": strava_activity.start_date,
            "elapsed_time": strava_activity.elapsed_time,
            "moving_time": strava_activity.moving_time,
            "description": strava_activity.description,
            "workout_type": strava_activity.workout_type,
            "distance": unithelper.meters(strava_activity.distance),
            "total_elevation_gain": unithelper.meters(
                strava_activity.total_elevation_gain
            ),
            "gear": strava_activity.gear_id,
            "commute": strava_activity.commute,
        }

        # find or create the activity type
        fields_map["activity_type"], created = ActivityType.objects.get_or_create(
            name=strava_activity.type
        )

        # resolve foreign key relationship for gear if any
        if strava_activity.gear_id:
            fields_map["gear"], created = Gear.objects.get_or_create(
                strava_id=strava_activity.gear_id, athlete=self.athlete
            )
            # Retrieve the gear information from Strava if gear is new.
            if created:
                fields_map["gear"].update_from_strava()

        # transform text field to empty if None
        if strava_activity.description is None:
            fields_map["description"] = ""

        # update the activity in the Database
        for key, value in fields_map.items():
            setattr(self, key, value)

        self.save()

    def save_streams_from_strava(self):
        """
        save streams from Strava to a pandas DataFrame using the custom
        Model field DataFrameField.
        """

        raw_streams = self.get_streams_from_strava()
        if raw_streams:
            self.streams = DataFrame(
                {key: stream.data for key, stream in raw_streams.items()}
            )
            self.save(update_fields=["streams"])
            return True

    def get_streams_from_strava(self, resolution="low"):
        """
        Return activity streams from Strava: Time, Altitude, Distance and Moving.

        Only activities with all four required types of stream present will be returned.
        Setting a 'low' resolution provides free downsampling of the data
        for better accuracy in the prediction.
        """

        STREAM_TYPES = ["time", "altitude", "distance", "moving"]

        # exclude manually created activities because they have no streams
        if not self.manual:
            strava_client = self.athlete.strava_client

            raw_streams = strava_client.get_activity_streams(
                self.strava_id, types=STREAM_TYPES, resolution=resolution
            )

            # ensure that we have all stream types and that they all contain values
            if all(stream_type in raw_streams for stream_type in STREAM_TYPES) and all(
                raw_stream.original_size > 0 for key, raw_stream in raw_streams.items()
            ):
                return raw_streams

    def get_training_data(self):
        """
        return actvity data for training the linear regression model.
        """

        # load activity streams as a DataFrame
        activity_data = self.streams

        # calculate gradient in percents, pace in minutes/kilometer and cumulative elevation gain
        activity_data["step_distance"] = activity_data.distance.diff()
        activity_data["gradient"] = (
            activity_data.altitude.diff() / activity_data.step_distance * 100
        )
        activity_data["pace"] = activity_data.time.diff() / activity_data.step_distance
        activity_data["cumulative_elevation_gain"] = activity_data.altitude.diff()[
            activity_data.altitude.diff() >= 0
        ].cumsum()
        activity_data[
            "cumulative_elevation_gain"
        ] = activity_data.cumulative_elevation_gain.fillna(method="ffill").fillna(
            value=0
        )

        # remove rows with empty gradient or empty pace
        columns = ["gradient", "pace"]
        activity_data = activity_data[activity_data[columns].notnull().all(1)].copy()

        # add activity information to every row
        activity_properties = {
            "strava_id": self.strava_id,
            "start_date": self.start_date,
            "total_elevation_gain": self.total_elevation_gain,
            "total_distance": self.distance,
            "gear": self.gear.strava_id if self.gear else "None",
            "workout_type": self.get_workout_type_display()
            if self.workout_type or self.workout_type == 0
            else "None",
            "commute": self.commute,
        }

        return activity_data.assign(
            **{key: value for key, value in activity_properties.items()}
        )


class ActivityType(models.Model):
    """
    ActivityType is used to define default performance values for each type of activity.
    The choice of available activities is limited to the ones available on Strava:
    http://developers.strava.com/docs/reference/#api-models-ActivityType
    """

    # Strava activity types
    ALPINESKI = "AlpineSki"
    BACKCOUNTRYSKI = "BackcountrySki"
    CANOEING = "Canoeing"
    CROSSFIT = "Crossfit"
    EBIKERIDE = "EBikeRide"
    ELLIPTICAL = "Elliptical"
    GOLF = "Golf"
    HANDCYCLE = "Handcycle"
    HIKE = "Hike"
    ICESKATE = "IceSkate"
    INLINESKATE = "InlineSkate"
    KAYAKING = "Kayaking"
    KITESURF = "Kitesurf"
    NORDICSKI = "NordicSki"
    RIDE = "Ride"
    ROCKCLIMBING = "RockClimbing"
    ROLLERSKI = "RollerSki"
    ROWING = "Rowing"
    RUN = "Run"
    SAIL = "Sail"
    SKATEBOARD = "Skateboard"
    SNOWBOARD = "Snowboard"
    SNOWSHOE = "Snowshoe"
    SOCCER = "Soccer"
    STAIRSTEPPER = "StairStepper"
    STANDUPPADDLING = "StandUpPaddling"
    SURFING = "Surfing"
    SWIM = "Swim"
    VELOMOBILE = "Velomobile"
    VIRTUALRIDE = "VirtualRide"
    VIRTUALRUN = "VirtualRun"
    WALK = "Walk"
    WEIGHTTRAINING = "WeightTraining"
    WHEELCHAIR = "Wheelchair"
    WINDSURF = "Windsurf"
    WORKOUT = "Workout"
    YOGA = "Yoga"

    ACTIVITY_NAME_CHOICES = [
        (ALPINESKI, "Alpine Ski"),
        (BACKCOUNTRYSKI, "Backcountry Ski"),
        (CANOEING, "Canoeing"),
        (CROSSFIT, "Crossfit"),
        (EBIKERIDE, "E-Bike Ride"),
        (ELLIPTICAL, "Elliptical"),
        (GOLF, "Golf"),
        (HANDCYCLE, "Handcycle"),
        (HIKE, "Hike"),
        (ICESKATE, "Ice Skate"),
        (INLINESKATE, "Inline Skate"),
        (KAYAKING, "Kayaking"),
        (KITESURF, "Kitesurf"),
        (NORDICSKI, "Nordic Ski"),
        (RIDE, "Ride"),
        (ROCKCLIMBING, "Rock Climbing"),
        (ROLLERSKI, "Roller Ski"),
        (ROWING, "Rowing"),
        (RUN, "Run"),
        (SAIL, "Sail"),
        (SKATEBOARD, "Skateboard"),
        (SNOWBOARD, "Snowboard"),
        (SNOWSHOE, "Snowshoe"),
        (SOCCER, "Soccer"),
        (STAIRSTEPPER, "Stair Stepper"),
        (STANDUPPADDLING, "Stand-Up Paddling"),
        (SURFING, "Surfing"),
        (SWIM, "Swim"),
        (VELOMOBILE, "Velomobile"),
        (VIRTUALRIDE, "Virtual Ride"),
        (VIRTUALRUN, "Virtual Run"),
        (WALK, "Walk"),
        (WEIGHTTRAINING, "Weight Training"),
        (WHEELCHAIR, "Wheelchair"),
        (WINDSURF, "Windsurf"),
        (WORKOUT, "Workout"),
        (YOGA, "Yoga"),
    ]

    SUPPORTED_ACTIVITY_TYPES = {
        BACKCOUNTRYSKI,
        EBIKERIDE,
        HANDCYCLE,
        HIKE,
        INLINESKATE,
        NORDICSKI,
        RIDE,
        ROCKCLIMBING,
        ROLLERSKI,
        RUN,
        SNOWSHOE,
        VELOMOBILE,
        VIRTUALRIDE,
        VIRTUALRUN,
        WALK,
        WHEELCHAIR,
    }

    name = models.CharField(max_length=24, choices=ACTIVITY_NAME_CHOICES, unique=True)

    # fallback performance values when the athlete has no model trained for the activity type
    # list of regression coefficients as trained by the regression model
    regression_coefficients = NumpyArrayField(
        models.FloatField(), default=get_default_array
    )

    # flat pace in seconds per meter, aka the intercept of the regression.
    flat_parameter = models.FloatField(default=0.36)  # 6:00/km or 10km/h

    # gear categories in the absence of a prediction model for the athlete
    gear_categories = NumpyArrayField(
        models.CharField(max_length=50),
        default=get_default_category,
    )

    # workout_type categories in the absence of a prediction model for the athlete
    workout_type_categories = NumpyArrayField(
        models.CharField(max_length=50),
        default=get_default_category,
    )

    # min and max plausible gradient and speed to filter outliers in activity data.
    min_pace = models.FloatField(default=0.12)  # 2:00/km or 30km/h
    max_pace = models.FloatField(default=2.4)  # 40:00/km or 1.5 km/h
    min_gradient = models.FloatField(default=-100.0)  # 100% or -45°
    max_gradient = models.FloatField(default=100.0)  # 100% or 45°

    def __str__(self):
        return self.name


class ActivityPerformance(TimeStampedModel):
    """
    Intermediate model for athlete - activity type
    The perfomance of an athlete is calculated using his Strava history.

    The base assumption is that the pace of the athlete depends
    on the *slope* of the travelled distance.

    Based on the athlete's history on strava, we train a linear regression model
    to predict the athlete's pace on a route.
    """

    athlete = models.ForeignKey("Athlete", on_delete=models.CASCADE)
    activity_type = models.ForeignKey("ActivityType", on_delete=models.PROTECT)

    # gear categories saved by the one-hot encoder in the prediction pipeline
    gear_categories = NumpyArrayField(
        models.CharField(max_length=50),
        default=get_default_category,
    )

    # workout_type categories saved by the one-hot encoder in the prediction pipeline
    workout_type_categories = NumpyArrayField(
        models.CharField(max_length=50),
        default=get_default_category,
    )

    # numpy array of regression coefficients as trained by the regression model
    regression_coefficients = NumpyArrayField(
        models.FloatField(), default=get_default_array
    )

    # intercept of the linear regression, which corresponds to pace in seconds per meter on flat terrain.
    flat_parameter = models.FloatField(default=0.36)  # 10km/h

    # reliability and cross_validation scores of the prediction model between 0.0 and 1.0
    model_score = models.FloatField(default=0.0)
    cv_scores = NumpyArrayField(models.FloatField(), default=get_default_array)

    def __str__(self):
        return "{} - {} - {:.2%}".format(
            self.athlete.user.username, self.activity_type.name, self.model_score
        )

    def get_training_data(self, start_year=None):
        """
        retrieve streams and information from selected activities to train the linear regression model.
        """

        target_activities = Activity.objects.filter(
            athlete=self.athlete,
            activity_type=self.activity_type,
            streams__isnull=False,
        )

        if start_year:
            target_activities = target_activities.filter(
                start_date__year__gte=start_year
            )

        # collect activity_data into a pandas DataFrame
        observations = DataFrame()
        for activity in target_activities:
            observations = observations.append(
                activity.get_training_data(), sort=True, ignore_index=True
            )

        return observations

    def remove_outliers(self, observations):
        """
        filter speed or gradient outliers from observation.
        """

        return observations[
            (observations.pace > self.activity_type.min_pace)
            & (observations.pace < self.activity_type.max_pace)
            & (observations.gradient > self.activity_type.min_gradient)
            & (observations.gradient < self.activity_type.max_gradient)
        ]

    def train_prediction_model(self, start_year=2017):
        """
        train prediction model with athlete data for the target activity.
        exclude activities older than the `start_year` parameter.

        """

        # get activity data from hdf5 files
        observations = self.get_training_data(start_year=start_year)
        if observations.empty:
            return (
                f"No training data found for activity type: {self.activity_type.name}"
            )

        # remove outliers
        data = self.remove_outliers(observations)

        # train prediction model
        prediction_model = PredictionModel()
        feature_columns = (
            prediction_model.numerical_columns + prediction_model.categorical_columns
        )
        prediction_model.train(
            y=data["pace"],
            x=data[feature_columns].fillna(value="None"),
        )
        # save model score, coefficients and intercept for future predictions
        self.model_score = prediction_model.model_score
        self.cv_scores = prediction_model.cv_scores

        regression = prediction_model.pipeline.named_steps["ridge"]
        self.regression_coefficients = regression.coef_
        self.flat_parameter = regression.intercept_

        (
            self.gear_categories,
            self.workout_type_categories,
        ) = prediction_model.onehot_encoder_categories

        self.save()

        message = f"Model successfully trained with {data.shape[0]} observations. "
        message += f"Model score: {self.model_score}, cross-validation score: {self.cv_scores}. "
        return message


class Gear(models.Model):
    """
    Small helper model to save gear from Strava.
    """

    strava_id = models.CharField(max_length=24, unique=True)
    name = models.CharField(max_length=100, blank=True)
    brand_name = models.CharField(max_length=100, blank=True)
    athlete = models.ForeignKey(
        "Athlete", on_delete=models.CASCADE, related_name="gears"
    )

    def __str__(self):
        return "{0} - {1}".format(self.brand_name, self.name)

    def update_from_strava(self):
        # retrieve gear info from Strava
        strava_gear = self.athlete.strava_client.get_gear(self.strava_id)

        self.name = strava_gear.name
        if strava_gear.brand_name is not None:
            self.brand_name = strava_gear.brand_name

        # save
        self.save()
