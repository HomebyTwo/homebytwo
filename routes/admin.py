from django.contrib.gis import admin

# Register your models here.

from .models import Route

admin.site.register(Route, admin.OSMGeoAdmin)