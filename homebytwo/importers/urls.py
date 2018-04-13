from django.conf.urls import url

from . import views

urlpatterns = [

    # importers: /import/
    url(
        r'^$',
        views.index,
        name='importers_index'
    ),

    # /import/strava/
    url(
        r'^strava/$',
        views.strava_routes,
        name='strava_routes'
    ),

    # /import/strava/1234567/
    url(
        r'^strava/(?P<source_id>[0-9]+)/$',
        views.strava_route,
        name='strava_route'
    ),

    # /import/strava/connect/
    url(
        r'^strava/connect/$',
        views.strava_connect,
        name='strava_connect'
    ),

    # /import/strava/authorized/
    url(
        r'^strava/authorized/$',
        views.strava_authorized,
        name='strava_authorized'
    ),

    # /import/switzerland_mobility/
    url(
        r'^switzerland-mobility/$',
        views.switzerland_mobility_routes,
        name='switzerland_mobility_routes'
    ),

    # /import/switzerland_mobility/1234567/
    url(
        r'^switzerland-mobility/(?P<source_id>[0-9]+)/$',
        views.switzerland_mobility_route,
        name='switzerland_mobility_route'
    ),

    # /import/switzerland_mobility/login/
    url(
        r'^switzerland-mobility/login/$',
        views.switzerland_mobility_login,
        name='switzerland_mobility_login'
    ),
]
