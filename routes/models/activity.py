from django.contrib.gis.db import models


class ActivityType(models.Model):
    name = models.CharField(max_length=100)

    # Default values for ActivityPerformance
    # Vertical speed up used for time calculation in meters/hour
    default_vam_up = models.FloatField(default=400)
    # Vertical speed down used for time calculation in meters/hour
    default_vam_down = models.FloatField(default=2000)
    # Horizontal speed used for time calculation in meters/hour
    default_flat_pace = models.FloatField(default=4000)

    def __str__(self):
        return self.name

    def __unicode__(self):
        return self.name


class ActivityPerformance(models.Model):
    # Intermediate model for athlete - activity type
    athlete = models.ForeignKey('Athlete', on_delete=models.CASCADE)
    activity_type = models.ForeignKey('ActivityType', on_delete=models.CASCADE)

    # Vertical speed up used for time calculation in meters/hour
    vam_up = models.FloatField(default=400)
    # Vertical speed down used for time calculation in meters/hour
    vam_down = models.FloatField(default=2000)
    # Horizontal speed used for time calculation in meters/hour
    flat_pace = models.FloatField(default=4000)
