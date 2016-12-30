from django.conf.urls import url

from . import views

urlpatterns = [

    # http://homebytwo.ch/importers/strava/
    url(
            r'^strava/$',
            views.strava_index,
            name='strava_index'
        ),

    # http://homebytwo.ch/importers/strava/connect/
    url(
            r'^strava/connect/$',
            views.strava_connect,
            name='strava_connect'
        ),

    # http://homebytwo.ch/importers/strava/authorized/
    url(
            r'^strava/authorized/$',
            views.strava_authorized,
            name='strava_authorized'
        ),

    # http://homebytwo.ch/importers/switzerland_mobility/
    url(
            r'^switzerland-mobility/$',
            views.switzerland_mobility_index,
            name='switzerland_mobility_index'
        ),
]
