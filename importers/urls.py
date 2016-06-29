from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^strava/$', views.strava_index, name='strava_index'),
    url(r'^strava/authorized/$', views.strava_authorized, name='strava_authorized'),
    url(r'^strava/routes/(?P<strava_route_id>[0-9]+)/$', views.strava_detail, name='strava_edit'),
    url(r'^strava/$', views.switzerland_mobility_index, name='switzerland_mobility_index'),
]