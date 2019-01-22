from django.urls import include, path

from . import views

app_name = 'routes'

urlpatterns = [
    # index
    path('', views.routes, name='routes'),

    # display route details by id
    # example: /routes/5/
    path('<int:pk>/', include([
        path('', views.route, name='route'),
        path('checkpoints/', views.route_checkpoints_list, name='checkpoints_list'),
    ])),

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
]
