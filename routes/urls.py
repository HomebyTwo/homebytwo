from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    # ex: /routes/5/
    url(r'^(?P<route_id>[0-9]+)/$', views.by_id, name='by_id'),
	# ex: /routes/tour-dai-super-combo/
	url(r'^(?P<slug>[-\w\d]+)/$', views.detail, name='detail'),
    # ex: /routes/5/edit/
    url(r'^(?P<route_id>[0-9]+)/edit/$', views.edit, name='edit'),
]