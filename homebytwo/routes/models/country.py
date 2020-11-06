from django.contrib.gis.db import models


class Country(models.Model):
    """
    Country geometries from https://github.com/datasets/geo-countries/
    Country codes from https://github.com/datasets/country-codes
    """
    iso3 = models.CharField(max_length=3, primary_key=True)
    iso2 = models.CharField(max_length=2)
    name = models.CharField(max_length=250)
    geom = models.MultiPolygonField(srid=4326)

    def __str__(self):
        return self.name
