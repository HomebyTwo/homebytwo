from django.db import models


class TimeStampedModel(models.Model):
    """
    An abstract base class model that provides self-updating
    `created` and `updated` fields.
    """

    created = models.DateTimeField("Time of last update", auto_now_add=True)
    updated = models.DateTimeField("Time of creation", auto_now=True)

    class Meta:
        abstract = True

    def __str__(self):
        return "created: {}".format(self.created)
