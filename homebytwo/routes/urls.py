from django.urls import include, path

from . import views

app_name = "routes"

urlpatterns = [
    # display athlete routes list: /routes/
    path("", views.view_routes, name="routes"),
    # single route
    path(
        "<int:pk>/",
        include(
            [
                # display route: routes/5/
                path("", views.view_route, name="route"),
                # retrieve route schedule (start, checkpoints, finish) as json:
                # routes/5/schedule/
                path(
                    "schedule/",
                    include(
                        [
                            path("", views.route_schedule, name="schedule"),
                            path(
                                # get and post route checkpoints as json:
                                # routes/5/schedule/checkpoints/
                                "checkpoints/",
                                views.route_checkpoints_edit,
                                name="edit_checkpoints",
                            ),
                            path(
                                # get and post route start as json:
                                # routes/5/schedule/start/
                                "start/",
                                views.route_start_edit,
                                name="edit_start",
                            ),
                            path(
                                # get and post route finish as json:
                                # routes/5/schedule/finish/
                                "finish/",
                                views.route_finish_edit,
                                name="edit_finish",
                            ),
                        ]
                    ),
                ),
                # edit route: /routes/5/edit/
                path("edit/", views.RouteEdit.as_view(), name="edit"),
                # update route with remote data: /routes/5/update/
                path("update/", views.RouteUpdate.as_view(), name="update"),
                # route delete: /routes/5/delete/
                path("delete/", views.RouteDelete.as_view(), name="delete"),
                # route as gpx: /routes/5/gpx/
                path("gpx/", views.download_route_gpx, name="gpx"),
                # garmin upload: /routes/5/garmin_upload/
                path(
                    "garmin_upload/", views.upload_route_to_garmin, name="garmin_upload"
                ),
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
                    "import/",
                    views.import_strava_activities,
                    name="import_activities",
                ),
                path(
                    "import-streams/",
                    views.import_strava_streams,
                    name="import_streams",
                ),
                path(
                    "train-models/",
                    views.train_prediction_models,
                    name="train_models",
                ),
            ]
        ),
    ),
    # callback URL for Strava webhooks
    path("webhook/", views.strava_webhook, name="strava_webhook"),
]
