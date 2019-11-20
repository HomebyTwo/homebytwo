from django.contrib.gis.db import models
from django.contrib.postgres.fields import JSONField

from ...core.models import TimeStampedModel


class WebhookTransaction(TimeStampedModel):
    UNPROCESSED = 1
    PROCESSED = 2
    ERROR = 3
    SKIPPED = 4

    STATUSES = (
        (UNPROCESSED, "Unprocessed"),
        (PROCESSED, "Processed"),
        (ERROR, "Error"),
        (SKIPPED, "Skipped"),
    )

    # time of generation on Strava side
    class Meta:
        ordering = ["-date_generated"]
    date_generated = models.DateTimeField()
    body = JSONField()
    request_meta = JSONField()
    status = models.PositiveIntegerField(choices=STATUSES, default=UNPROCESSED)

    def __str__(self):
        return "{0} - {1}".format(self.get_status_display(), self.date_generated)
