from django.contrib.gis import admin

# Register your models here.
from .models import WorldBorder

admin.site.register(WorldBorder, admin.OSMGeoAdmin)