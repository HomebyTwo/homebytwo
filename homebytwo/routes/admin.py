from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.contrib.gis import admin

from leaflet.admin import LeafletGeoAdmin

from .models import (
    Activity,
    ActivityPerformance,
    Athlete,
    Place,
    Route,
    WebhookTransaction,
    ActivityType,
)


class RouteAdmin(LeafletGeoAdmin):
    readonly_fields = ("source_link",)
    list_display = ["name", "athlete", "activity_type"]
    fieldsets = [
        (None, {"fields": ("name", "athlete", "activity_type")}),
        ("Map", {"fields": ("geom",)}),
        (
            "Source Information",
            {
                "fields": ("data_source", "source_id", "source_link"),
                "classes": ("collapse",),
            },
        ),
    ]


class PlaceAdmin(LeafletGeoAdmin):
    # Custom administration for Place
    fieldsets = [
        (None, {"fields": ["name", "description", "place_type", "altitude"]}),
        ("Map", {"fields": ["geom"]}),
    ]


class ActivityAdmin(LeafletGeoAdmin):
    list_display = ["name", "athlete", "activity_type"]


class ActivityPerformanceAdmin(LeafletGeoAdmin):
    list_display = ["athlete", "activity_type", "model_score"]


class AthleteInline(admin.StackedInline):
    model = Athlete
    can_delete = False


class UserAdmin(BaseUserAdmin):
    inlines = [
        AthleteInline,
    ]


admin.site.register(ActivityType)
admin.site.register(Route, RouteAdmin)
admin.site.register(Place, PlaceAdmin)
admin.site.register(Activity, ActivityAdmin)
admin.site.register(ActivityPerformance, ActivityPerformanceAdmin)
admin.site.register(WebhookTransaction)
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
