import django.views.static
from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

from homebytwo.landingpage import views as landingpage_views

urlpatterns = [

    # Landing Page URL patterns
    url(r'^$', landingpage_views.home, name="home"),
    url(r'^email-signup/$',
        landingpage_views.email_signup,
        name="email_signup"),
    url(r'^register/$',
        landingpage_views.register,
        name="register"),

    # URL patterns from other apps
    url(r'^routes/', include('homebytwo.routes.urls')),
    url(r'^import/', include('homebytwo.importers.urls')),
    url(r'^admin/', admin.site.urls),
    url('^', include('django.contrib.auth.urls')),
]

# Serve Media URL in development. This is only needed when using runserver.
if settings.DEBUG:
    urlpatterns = [
        url(r'^media/(?P<path>.*)$', django.views.static.serve,
            {'document_root': settings.MEDIA_ROOT, 'show_indexes': True}),
    ] + staticfiles_urlpatterns() + urlpatterns

    # serve Django Debug Toolbar in DEBUG mode
    import debug_toolbar
    urlpatterns = [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
