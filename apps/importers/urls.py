from django.conf.urls import url

from . import views

urlpatterns = [

    # importers: /import/
    url(
        r'^$',
        views.index,
        name='index'
    ),

    # /importers/strava/
    url(
        r'^strava/$',
        views.strava_routes,
        name='strava_routes'
    ),

    # /importers/strava/1234567/
    url(
        r'^strava/(?P<source_id>[0-9]+)/$',
        views.strava_route,
        name='strava_route'
    ),

    # /importers/strava/connect/
    url(
        r'^strava/connect/$',
        views.strava_connect,
        name='strava_connect'
    ),

    # /importers/strava/authorized/
    url(
        r'^strava/authorized/$',
        views.strava_authorized,
        name='strava_authorized'
    ),

    # /importers/switzerland_mobility/
    url(
        r'^switzerland-mobility/$',
        views.switzerland_mobility_routes,
        name='switzerland_mobility_routes'
    ),

    # /importers/switzerland_mobility/1234567/
    url(
        r'^switzerland-mobility/(?P<source_id>[0-9]+)/$',
        views.switzerland_mobility_route,
        name='switzerland_mobility_route'
    ),

    # /importers/switzerland_mobility/login/
    url(
        r'^switzerland-mobility/login/$',
        views.switzerland_mobility_login,
        name='switzerland_mobility_login'
    ),
]
