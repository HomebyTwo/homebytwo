from django.contrib.gis import admin

# Register your models here.

from .models import Track

admin.site.register(Track, admin.OSMGeoAdmin)