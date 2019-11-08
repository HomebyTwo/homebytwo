from django.contrib.gis.db import models
from stravalib import unithelper

from ...core.models import TimeStampedModel


def save_from_strava(strava_activity, athlete):
    """
    helper function to create or update a Strava activity based on
    information received from Strava.
    """

    # fields from the Strava API object mapped to the Activity Model
    mapped_values = {
        "name": strava_activity.name,
        "activity_type": strava_activity.type,
        "start_date": strava_activity.start_date,
        "elapsed_time": strava_activity.elapsed_time,
        "moving_time": strava_activity.moving_time,
        "description": strava_activity.description,
        "workout_type": strava_activity.workout_type,
        "distance": unithelper.meters(strava_activity.distance),
        "totalup": unithelper.meters(strava_activity.total_elevation_gain),
        "gear": strava_activity.gear_id,
    }

    # find or create the activity type
    mapped_values["activity_type"], created = ActivityType.objects.get_or_create(
        name=strava_activity.type
    )

    # resolve foreign key relationship for gear if any
    if strava_activity.gear_id is not None:
        mapped_values["gear"], created = Gear.objects.get_or_create(
            strava_id=strava_activity.gear_id, athlete=athlete
        )
        # Retrieve the gear information from Strava if gear is new.
        if created:
            mapped_values["gear"].update_from_strava()

    # create or update the activity in the Database
    activity, created = Activity.objects.update_or_create(
        strava_id=strava_activity.id,
        athlete=athlete,
        manual=strava_activity.manual,
        defaults=mapped_values,
    )

    return activity


class ActivityManager(models.Manager):
    def import_all_user_activities_from_strava(
        self, user, after=None, before=None, limit=0
    ):
        """
        fetches user activities from Strava, saves them to the Database and returns them

        Parameters:s
        'after': start date is after specified value (UTC). datetime.datetime, str or None.
        'before': start date is before specified value (UTC). datetime.datetime or str or None
        'limit': maximum activites retrieved. Integer

        See https://pythonhosted.org/stravalib/usage/activities.html#list-of-activities
        and https://developers.strava.com/playground/#/Activities/getLoggedInAthleteActivities
        """
        strava_activities = user.athlete.strava_client.get_activities(
            before=before, after=after, limit=limit
        )

        activities = []

        for strava_activity in strava_activities:
            activity = save_from_strava(strava_activity, user)
            activities.add(activity)

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
    totalup = models.FloatField("Total elevation gain in m", blank=True, null=True)

    # total duration of the activity in seconds as opposed to moving time
    elapsed_time = models.DurationField(
        "Total activity time as timedelta", blank=True, null=True
    )

    # time in movement during the activity
    moving_time = models.DurationField(
        "Movement time as timedelta", blank=True, null=True
    )

    # Workout Type as defined in Strava
    workout_type = models.SmallIntegerField(
        choices=WORKOUT_TYPE_CHOICES, blank=True, null=True
    )

    # Gear used if any
    gear = models.ForeignKey(
        "Gear",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="activities",
    )

    # Custom manager
    objects = ActivityManager()

    def __str__(self):
        return "{0} - {1}".format(self.activity_type, self.name)

    def update_from_strava(self):
        # retrieve activity from Strava and update it.
        strava_activity = self.athlete.strava_client.get_activity(self.strava_id)
        save_from_strava(strava_activity, self.athlete)

    def get_streams_from_strava(self, resolution="low"):
        """
        Return activity streams from Strava: Time, Altitude and Distance.
        This is the data that will be used for calculating performance values.

        Only activities with all three required types of stream present will be used.
        Setting a 'low' resolution provides free downsampling of the data
        for better accuracy in the prediction.
        """
        # exclude manually created activities because they have no streams
        if not self.manual:
            STREAM_TYPES = ["time", "altitude", "distance"]
            strava_client = self.athlete.strava_client

            raw_streams = strava_client.get_activity_streams(
                self.strava_id, types=STREAM_TYPES, resolution=resolution
            )

            if all(stream_type in raw_streams for stream_type in STREAM_TYPES):
                return raw_streams


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

    name = models.CharField(max_length=24, choices=ACTIVITY_NAME_CHOICES, unique=True)

    # Default values for ActivityPerformance

    # Slope squared parameter of the regression model
    slope_squared_param = models.FloatField(default=7.0)

    # Slope parameter of the regression model
    slope_param = models.FloatField(default=1.0)

    # Flat parameter. This is the default pace in s per meter on flat terrain
    flat_param = models.FloatField(default=0.36)  # 6:00/km

    # Total elevation gain parameter of the regression model
    total_elevation_gain_param = models.FloatField(default=0.1)

    def __str__(self):
        return self.name


class ActivityPerformance(models.Model):
    """
    Intermediate model for athlete - activity type
    The perfomance of an athlete is calculated using his Strava history.

    The base assumption is that the pace of the athlete depends
    on the *slope* of the travelled distance.

    Based on the athlete's performance on strava,
    we estimate an equation for the pace for each activity.

        flat_pace = slope_squared_param * slope**2 +
                    slope_param * slope +
                    flat_param +
                    total_elevation_gain_param * total_elevation_gain

    Params are fitted using a robust linear model.

    """

    athlete = models.ForeignKey("Athlete", on_delete=models.CASCADE)
    activity_type = models.ForeignKey("ActivityType", on_delete=models.PROTECT)

    # Slope squared parameter of the regression model
    slope_squared_param = models.FloatField(default=7.0)

    # Slope parameter of the regression model
    slope_param = models.FloatField(default=1.0)

    # Flat parameter. This is the default pace in s per meter on flat terrain
    flat_param = models.FloatField(default=0.36)  # 6:00/km

    # Total elevation gain parameter of the regression model
    total_elevation_gain_param = models.FloatField(default=0.1)

    def __str__(self):
        return "{0} - {1}".format(self.athlete.user.username, self.activity_type.name)


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
