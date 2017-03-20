from django.conf.urls import url

from . import views

app_name = 'routes'

urlpatterns = [
    # index
    url(r'^$', views.routes, name='routes'),

    # display route details by id
    # example: /routes/5/
    url(r'^(?P<pk>[0-9]+)/$', views.route, name='route'),

    # edit route
    # ex: /routes/5/edit/
    url(r'^(?P<pk>[0-9]+)/edit/$', views.RouteEdit.as_view(), name='edit'),

    # change the route image
    # ex: /routes/5/image/
    url(r'^(?P<pk>[0-9]+)/image/$', views.ImageFormView.as_view(), name='image'),

    # route delete
    # ex: /routes/5/delete/
    url(r'^(?P<pk>[0-9]+)/delete/$', views.RouteDelete.as_view(), name='delete'),
]
