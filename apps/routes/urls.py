from django.conf.urls import url

from . import views

app_name = 'routes'

urlpatterns = [
    # index
    url(r'^$', views.routes, name='routes'),

    # route detail by id
    # example: /routes/5/
    url(r'^(?P<pk>[0-9]+)/$', views.route, name='route'),

    # route edit
    # ex: /routes/5/edit/
    url(r'^(?P<pk>[0-9]+)/edit/$', views.edit, name='edit'),

    # route image
    # ex: /routes/5/image/
    url(r'^(?P<pk>[0-9]+)/image/$', views.ImageFormView.as_view(), name='image'),
]
