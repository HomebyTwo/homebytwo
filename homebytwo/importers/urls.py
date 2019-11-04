from django.urls import path

from . import views

urlpatterns = [

    # importers: /import/
    path(
        '',
        views.index,
        name='importers_index'
    ),

    # /import/strava/
    path(
        'strava/',
        views.strava_routes,
        name='strava_routes'
    ),

    # /import/strava/1234567/
    path(
        'strava/<int:source_id>/',
        views.strava_route,
        name='strava_route'
    ),

    # /import/strava/connect/
    path(
        'strava/connect/',
        views.strava_connect,
        name='strava_connect'
    ),

    # /import/switzerland_mobility/
    path(
        'switzerland-mobility/',
        views.switzerland_mobility_routes,
        name='switzerland_mobility_routes'
    ),

    # /import/switzerland_mobility/1234567/
    path(
        'switzerland-mobility/<int:source_id>/',
        views.switzerland_mobility_route,
        name='switzerland_mobility_route'
    ),

    # /import/switzerland_mobility/login/
    path(
        'switzerland-mobility/login/',
        views.switzerland_mobility_login,
        name='switzerland_mobility_login'
    ),
]
