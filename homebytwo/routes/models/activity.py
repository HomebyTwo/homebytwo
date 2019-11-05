from django.contrib.gis.db import models


class ActivityManager(models.Manager):

    def import_all_user_activities_from_strava(self, user, after=None, before=None, limit=0):
        """
        retrieves all user activities from Strava and saves them to the Database.

        'after': start date is after specified value (UTC). datetime.datetime, str or None.
        'before': start date is before specified value (UTC). datetime.datetime or str or None
        'limit': maximum activites retrieved. Integer

        See https://pythonhosted.org/stravalib/usage/activities.html#list-of-activities
        and https://developers.strava.com/playground/#/Activities/getLoggedInAthleteActivities
        """

        kwargs = {
            'after': after,
            'before': before,
            'limit': limit
        }

        strava_activities = user.athlete.strava_client.get_activities(**kwargs)

        for strava_activity in strava_activities:

            # Retrieve the gear information from Strava if it does not yet exist in the database
            if strava_activity.gear_id is not None:
                gear, created = Gear.objects.get_or_create(strava_id=strava_activity.gear_id,
                                                           athlete=user.athlete)

                if created:
                    gear.update_from_strava()
            else:
                gear = None

            # Create the related ActivityType if it does not yet exist in the database
            activity_type, created = ActivityType.objects.get_or_create(name=strava_activity.type)

            # Create or update the activity in the Database
            defaults = {
                'name': strava_activity.name,
                'gear': gear,
                'workout_type': strava_activity.workout_type,
                'activity_type': activity_type,
            }

            activity, created = self.update_or_create(
                strava_id=strava_activity.id,
                athlete=user.athlete,
                start_date=strava_activity.start_date,
                manual=strava_activity.manual,
                defaults=defaults,
            )


class Activity(models.Model):
    """
    All activities published by the athletes on Strava.
    User activities used to calculate performance by activity type.
    """

    WORKOUT_TYPE_CHOICES = [
        (None, 'None'),
        ('0', 'default run'),
        ('1', 'race run'),
        ('2', 'long run'),
        ('3', 'workout run'),
        ('10', 'default ride'),
        ('11', 'race ride'),
        ('12', 'workout ride'),
    ]

    # name of the activity as imported from Strava
    name = models.CharField(max_length=255)

    # Activity ID on Strava
    strava_id = models.BigIntegerField(unique=True)

    # Athlete whose activities have been imported from Strava
    athlete = models.ForeignKey('Athlete', on_delete=models.CASCADE)

    # Athlete whose activities have been imported from Strava
    activity_type = models.ForeignKey('ActivityType', on_delete=models.PROTECT)

    # Workout Type as defined in Strava
    workout_type = models.SmallIntegerField(choices=WORKOUT_TYPE_CHOICES, blank=True, null=True)

    # Gear used if any
    gear = models.ForeignKey('Gear', on_delete=models.SET_NULL, blank=True, null=True)

    # Starting date and time of the activity in UTC
    start_date = models.DateTimeField()

    # Was the activity created manually? If yes there are no associated data streams.
    manual = models.BooleanField(default=False)

    # Custom manager
    objects = ActivityManager()

    def __str__(self):
        return '{0} - {1}'.format(self.activity_type, self.name)

    def update_from_strava(self):
        # retrieve activity from Strava
        strava_activity = self.athlete.strava_client.get_activity(self.strava_id)

        # Create the related ActivityType if it does not yet exist in the database
        activity_type, created = ActivityType.objects.get_or_create(name=strava_activity.type)

        # Retrieve the gear information from Strava if it does not yet exist in the database
        if strava_activity.gear_id is not None:
            gear, created = Gear.objects.get_or_create(strava_id=strava_activity.gear_id,
                                                       athlete=self.athlete)

            if created:
                gear.update_from_strava()

        self.name = strava_activity.name
        self.activity_type = activity_type
        self.workout_type = strava_activity.workout_type
        self.gear = gear
        self.save()


class ActivityType(models.Model):
    """
    ActivityType is used to define default performance values for each type of activity.
    The choice of available activities is limited to the ones available on Strava:
    http://developers.strava.com/docs/reference/#api-models-ActivityType
    """

    # Strava activity types
    ACTIVITY_NAME_CHOICES = [
        ('AlpineSki', 'Alpine Ski'),
        ('BackcountrySki', 'Backcountry Ski'),
        ('Canoeing', 'Canoeing'),
        ('Crossfit', 'Crossfit'),
        ('EBikeRide', 'E-Bike Ride'),
        ('Elliptical', 'Elliptical'),
        ('Golf', 'Golf'),
        ('Handcycle', 'Handcycle'),
        ('Hike', 'Hike'),
        ('IceSkate', 'Ice Skate'),
        ('InlineSkate', 'Inline Skate'),
        ('Kayaking', 'Kayaking'),
        ('Kitesurf', 'Kitesurf'),
        ('NordicSki', 'Nordic Ski'),
        ('Ride', 'Ride'),
        ('RockClimbing', 'Rock Climbing'),
        ('RollerSki', 'Roller Ski'),
        ('Rowing', 'Rowing'),
        ('Run', 'Run'),
        ('Sail', 'Sail'),
        ('Skateboard', 'Skateboard'),
        ('Snowboard', 'Snowboard'),
        ('Snowshoe', 'Snowshoe'),
        ('Soccer', 'Soccer'),
        ('StairStepper', 'Stair Stepper'),
        ('StandUpPaddling', 'Stand-Up Paddling'),
        ('Surfing', 'Surfing'),
        ('Swim', 'Swim'),
        ('Velomobile', 'Velomobile'),
        ('VirtualRide', 'Virtual Ride'),
        ('VirtualRun', 'Virtual Run'),
        ('Walk', 'Walk'),
        ('WeightTraining', 'Weight Training'),
        ('Wheelchair', 'Wheelchair'),
        ('Windsurf', 'Windsurf'),
        ('Workout', 'Workout'),
        ('Yoga', 'Yoga'),
    ]

    name = models.CharField(max_length=24, choices=ACTIVITY_NAME_CHOICES)

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
    athlete = models.ForeignKey('Athlete', on_delete=models.CASCADE)
    activity_type = models.ForeignKey('ActivityType', on_delete=models.PROTECT)

    # Slope squared parameter of the regression model
    slope_squared_param = models.FloatField(default=7.0)

    # Slope parameter of the regression model
    slope_param = models.FloatField(default=1.0)

    # Flat parameter. This is the default pace in s per meter on flat terrain
    flat_param = models.FloatField(default=0.36)  # 6:00/km

    # Total elevation gain parameter of the regression model
    total_elevation_gain_param = models.FloatField(default=0.1)

    def __str__(self):
        return '{0} - {1}'.format(self.athlete.user.username,
                                  self.activity_type.name)


class Gear(models.Model):
    """
    Small helper model to save gear from Strava.
    """
    strava_id = models.CharField(max_length=24, unique=True)
    name = models.CharField(max_length=100, blank=True)
    brand_name = models.CharField(max_length=100, blank=True)
    athlete = models.ForeignKey('Athlete', on_delete=models.CASCADE)

    def __str__(self):
        return '{0} - {1}'.format(self.brand_name, self.name)

    def update_from_strava(self):
        # retrieve gear info from Strava
        strava_gear = self.athlete.strava_client.get_gear(self.strava_id)

        self.name = strava_gear.name
        if strava_gear.brand_name is not None:
            self.brand_name = strava_gear.brand_name

        # save
        self.save()
