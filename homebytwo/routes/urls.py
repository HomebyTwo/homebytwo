from django.urls import path

from . import views

app_name = 'routes'

urlpatterns = [
    # index
    path('', views.routes, name='routes'),

    # display route details by id
    # example: /routes/5/
    path('<int:pk>/', views.route, name='route'),

    # edit route
    # ex: /routes/5/edit/
    path('<int:pk>/edit/', views.RouteEdit.as_view(), name='edit'),

    # change the route image
    # ex: /routes/5/image/
    path('<int:pk>/image/', views.ImageFormView.as_view(), name='image'),

    # route delete
    # ex: /routes/5/delete/
    path('<int:pk>/delete/', views.RouteDelete.as_view(), name='delete'),

    # list of Strava activities for the athlete
    path('activities/', views.ActivityList.as_view(), name='activities'),

    # callback URL for Strava webhooks
    path('webhook/', views.strava_webhook, name='strava_webhook')
]
