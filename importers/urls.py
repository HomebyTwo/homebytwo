from django.conf.urls import url

from . import views

urlpatterns = [

    # /importers/strava/
    url(
            r'^strava/$',
            views.strava_index,
            name='strava_index'
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
            views.switzerland_mobility_index,
            name='switzerland_mobility_index'
        ),

    # /importers/switzerland_mobility/
    url(
            r'^switzerland-mobility/(?P<switzerland_mobility_id>[0-9]+)/$',
            views.switzerland_mobility_detail,
            name='switzerland_mobility_detail'
        ),

    # /importers/switzerland_mobility/login
    url(
            r'^switzerland-mobility/login/$',
            views.switzerland_mobility_login,
            name='switzerland_mobility_login'
        ),
]
