from django.conf.urls import url

from . import views

app_name = 'routes'

urlpatterns = [
    # index
    url(r'^$', views.index, name='index'),

    # Importers index
    # importers: /import/
    url(r'^import/$', views.importers, name='importers'),

    # route detail by id
    # example: /routes/5/
    url(r'^(?P<route_id>[0-9]+)/$', views.by_id, name='by_id'),

    # route detail by slug
    # example: /routes/tour-dai-super-combo/
    url(r'^(?P<slug>[-\w\d]+)/$', views.detail, name='detail'),

    # route edit
    # ex: /routes/5/edit/
    url(r'^(?P<route_id>[0-9]+)/edit/$', views.edit, name='edit'),
]
