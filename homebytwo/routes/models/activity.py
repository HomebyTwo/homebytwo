from django.contrib.gis.db import models


class ActivityType(models.Model):
    name = models.CharField(max_length=100)

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
    activity_type = models.ForeignKey('ActivityType', on_delete=models.CASCADE)

    # Slope squared parameter of the regression model
    slope_squared_param = models.FloatField(default=7.0)

    # Slope parameter of the regression model
    slope_param = models.FloatField(default=1.0)

    # Flat parameter. This is the default pace in s per meter on flat terrain
    flat_param = models.FloatField(default=0.36)  # 6:00/km

    # Total elevation gain parameter of the regression model
    total_elevation_gain_param = models.FloatField(default=0.1)

    def __str__(self):
        return "{} - {}".format(
            self.athlete.user.username,
            self.activity_type.name
        )
