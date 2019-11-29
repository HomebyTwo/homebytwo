from django.urls import include, path

from . import views

app_name = "routes"

urlpatterns = [
    # index
    path("", views.routes, name="routes"),
    # display route
    # /routes/5/
    path(
        "<int:pk>/",
        include(
            [
                path("", views.route, name="route"),
                # display checkpoints
                path(
                    "checkpoints/",
                    views.route_checkpoints_list,
                    name="checkpoints_list",
                ),
            ]
        ),
    ),
    # edit route
    # /routes/5/edit/
    path("<int:pk>/edit/", views.RouteEdit.as_view(), name="edit"),
    # update route with remote data
    # /routes/5/update/
    path("<int:pk>/update/", views.RouteUpdate.as_view(), name="update"),
    # change the route image
    # /routes/5/image/
    path("<int:pk>/image/", views.ImageFormView.as_view(), name="image"),
    # route delete
    # /routes/5/delete/
    path("<int:pk>/delete/", views.RouteDelete.as_view(), name="delete"),
    # list of Strava activities for the athlete
    path(
        "activities/",
        include(
            [
                path("", views.ActivityList.as_view(), name="activities"),
                path(
                    "activities/import-strava/",
                    views.import_strava_activities,
                    name="import_strava",
                ),
            ]
        ),
    ),
    # import athlete's Strava activities
    path(
        "activities/import-strava/",
        views.import_strava_activities,
        name="import_strava",
    ),
    # callback URL for Strava webhooks
    path("webhook/", views.strava_webhook, name="strava_webhook"),
]
