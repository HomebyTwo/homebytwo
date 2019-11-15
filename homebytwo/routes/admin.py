from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.contrib.gis import admin

from leaflet.admin import LeafletGeoAdmin

from .models import (
    Activity,
    ActivityPerformance,
    ActivityType,
    Athlete,
    Place,
    Route,
    WebhookTransaction,
)

# Route admin
admin.site.register(Route, LeafletGeoAdmin)


class PlaceAdmin(LeafletGeoAdmin):
    # Custom administration for Place
    fieldsets = [
        (
            None,
            {'fields': ['name', 'description', 'place_type', 'altitude']}
        ),
        (
            'Date',
            {'fields': ['geom']}
        )
    ]


admin.site.register(Place, PlaceAdmin)
admin.site.register(ActivityType, LeafletGeoAdmin)
admin.site.register(ActivityPerformance)
admin.site.register(Activity)
admin.site.register(WebhookTransaction)


class AthleteInline(admin.StackedInline):
    model = Athlete
    can_delete = False


class UserAdmin(BaseUserAdmin):
    inlines = [AthleteInline, ]


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
