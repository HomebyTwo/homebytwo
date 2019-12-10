from django.urls import include, path

from . import views

app_name = "routes"

urlpatterns = [
    # display athlete routes list: /routes/
    path("", views.routes, name="routes"),

    # single route
    path(
        "<int:pk>/",
        include(
            [
                # display route: routes/5/
                path("", views.route, name="route"),
                # retrieve possible checkpoints as json: routes/5/checkpoints/
                path(
                    "checkpoints/",
                    views.route_checkpoints_list,
                    name="checkpoints_list",
                ),
                # edit route: /routes/5/edit/
                path("edit/", views.RouteEdit.as_view(), name="edit"),
                # update route with remote data: /routes/5/update/
                path("update/", views.RouteUpdate.as_view(), name="update"),
                # change the route image: /routes/5/image/
                path("image/", views.ImageFormView.as_view(), name="image"),
                # route delete: /routes/5/delete/
                path("delete/", views.RouteDelete.as_view(), name="delete"),
                # route as gpx: /routes/5/gpx/
                path("gpx/", views.download_route_gpx, name="as_gpx"),
                # garmin upload: /routes/5/garmin_upload/
                path("garmin_upload/", views.upload_route_to_garmin, name="garmin_upload"),
            ]
        ),
    ),


    # activities
    path(
        "activities/",
        include(
            [
                # list of Strava activities for the athlete: /routes/activities
                path("", views.ActivityList.as_view(), name="activities"),
                # import athlete's Strava activities
                path(
                    "import-strava/",
                    views.import_strava_activities,
                    name="import_strava",
                ),
            ]
        ),
    ),
    # callback URL for Strava webhooks
    path("webhook/", views.strava_webhook, name="strava_webhook"),
]
