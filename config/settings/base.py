from pathlib import Path

import dj_database_url

from .. import get_project_root_path
from . import get_env_variable

###################
# DJANGO SETTINGS #
###################

# A boolean that turns on/off debug mode. When set to ``True``, stack traces
# are displayed for error pages. Should always be set to ``False`` in
# production. Best set to ``True`` in dev.py

DEBUG = False

# Whether a user's session cookie expires when the Web browser is closed.

SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)

BASE_DIR = get_project_root_path()

ALLOWED_HOSTS = tuple(get_env_variable("ALLOWED_HOSTS", "").splitlines())

SECRET_KEY = get_env_variable("SECRET_KEY", "")

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "django.contrib.humanize",
    "social_django",
    "widget_tweaks",
    "djgeojson",
    "leaflet",
    "easy_thumbnails",
    "homebytwo.routes",
    "homebytwo.importers",
    "homebytwo.landingpage",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "social_django.middleware.SocialAuthExceptionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [Path(BASE_DIR, "homebytwo", "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "social_django.context_processors.backends",
                "social_django.context_processors.login_redirect",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "homebytwo.context_processor.gtm_context_processor",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
DATABASES = {"default": dj_database_url.parse(get_env_variable("DATABASE_URL"))}

# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Login Page and logout redirect

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/routes/"
LOGIN_ERROR_URL = "/login/"
LOGOUT_REDIRECT_URL = "/"

# Internationalization

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Europe/Zurich"
USE_TZ = True


# URL prefix for static files.

STATIC_URL = get_env_variable("STATIC_URL", "/static/")

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# This is usually not used in a dev env, hence the default value
# Example: "/home/media/media.lawrence.com/static/"

STATIC_ROOT = get_env_variable("STATIC_ROOT", "/tmp/static")


STATICFILES_DIRS = (Path(BASE_DIR, get_project_root_path("homebytwo/static")),)

# Absolute path to the directory where media files should be collected to.

MEDIA_ROOT = get_env_variable("MEDIA_ROOT", get_project_root_path("homebytwo/media"))
MEDIA_URL = get_env_variable("MEDIA_URL", "/media/")

THUMBNAIL_ALIASES = {
    "": {
        "thumb": {"size": (90, 90), "crop": True, "sharpen": True},
        "poster": {"size": (1434, 600), "crop": True, "details": True, "quality": 95},
    },
}

##############
# Celery #
##############

celery_broker_url = get_env_variable("celery_broker_url", "amqp://localhost")
celery_accept_content = ["application/json"]
celery_result_serializer = "json"
celery_task_serializer = "json"

#############
# Mailchimp #
#############

MAILCHIMP_API_KEY = get_env_variable("MAILCHIMP_API_KEY", "")
MAILCHIMP_LIST_ID = get_env_variable("MAILCHIMP_LIST_ID", "")

######################
# Google Tag Manager #
######################

GTM_CONTAINER_ID = get_env_variable("GTM_CONTAINER_ID", "")

###########
# Coda.io #
###########

CODA_API_KEY = get_env_variable("CODA_API_KEY", "")
CODA_DOC_ID = get_env_variable("CODA_DOC_ID", "")
CODA_TABLE_ID = get_env_variable("CODA_TABLE_ID", "")

##########
# Mapbox #
##########

# https://www.mapbox.com/studio/account/tokens/

MAPBOX_ACCESS_TOKEN = get_env_variable("MAPBOX_ACCESS_TOKEN", "")


###########
# Leaflet #
###########

# http://krzysztofzuraw.com/blog/2016/geodjango-leaflet-part-two.html

LEAFLET_CONFIG = {
    "DEFAULT_CENTER": (46.818188, 8.227512),
    "DEFAULT_ZOOM": 7,
    "scrollWheelZoom": False,
    "MIN_ZOOM": 3,
    "MAX_ZOOM": 18,
    "TILES": "https://api.mapbox.com/styles/v1/drixslecta/cipip6crl004wcnngbqlofo9z/tiles/256/{z}/{x}/{y}?access_token="
    + MAPBOX_ACCESS_TOKEN,
    "ATTRIBUTION_PREFIX": '<a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, Imagery &copy; <a href="http://mapbox.com">Mapbox</a>',
    "PLUGINS": {
        "Leaflet.encoded": {
            "js": [STATIC_URL + "/javascripts/Polyline.encoded.js"],
            "auto-include": True,
        },
    },
}

##########
# Strava #
##########

# Strava API URL for retrieving routes
STRAVA_ROUTE_URL = get_env_variable("STRAVA_ROUTE_URL", "")

# Strava Verification token for the Strava Webhook Events API
STRAVA_VERIFY_TOKEN = get_env_variable("STRAVA_VERIFY_TOKEN", "")

######################
# Django Social Auth #
######################

# http://python-social-auth.readthedocs.io/en/latest/configuration/django.html#installing
SOCIAL_AUTH_POSTGRES_JSONFIELD = True
SOCIAL_AUTH_URL_NAMESPACE = "social"

AUTHENTICATION_BACKENDS = (
    "social_core.backends.strava.StravaOAuth",
    "django.contrib.auth.backends.ModelBackend",
)

# Strava settings for django social auth, see https://www.strava.com/settings/api
SOCIAL_AUTH_STRAVA_KEY = get_env_variable("STRAVA_CLIENT_ID", "12186")
SOCIAL_AUTH_STRAVA_SECRET = get_env_variable("STRAVA_CLIENT_SECRET", "")
SOCIAL_AUTH_STRAVA_SCOPE = ["read", "read_all", "activity:read", "activity:read_all"]

SOCIAL_AUTH_STRAVA_PIPELINE = (
    "social_core.pipeline.social_auth.social_details",
    "social_core.pipeline.social_auth.social_uid",
    "social_core.pipeline.social_auth.auth_allowed",
    "social_core.pipeline.social_auth.social_user",
    "social_core.pipeline.user.get_username",
    "social_core.pipeline.user.create_user",
    "social_core.pipeline.social_auth.associate_user",
    "social_core.pipeline.social_auth.load_extra_data",
    "social_core.pipeline.user.user_details",
    "homebytwo.routes.auth_pipeline.import_strava",
)


########################
# Switzerland Mobility #
########################

# Collection of Switzerland Mobility URL to
# retrieve data from https://map.wanderland.ch/

SWITZERLAND_MOBILITY_LOGIN_URL = get_env_variable("SWITZERLAND_MOBILITY_LOGIN_URL", "")
SWITZERLAND_MOBILITY_LIST_URL = get_env_variable("SWITZERLAND_MOBILITY_LIST_URL", "")
SWITZERLAND_MOBILITY_META_URL = get_env_variable("SWITZERLAND_MOBILITY_META_URL", "")
SWITZERLAND_MOBILITY_ROUTE_URL = get_env_variable("SWITZERLAND_MOBILITY_ROUTE_URL", "")
SWITZERLAND_MOBILITY_ROUTE_DATA_URL = get_env_variable(
    "SWITZERLAND_MOBILITY_ROUTE_DATA_URL", ""
)

##################
# GARMIN CONNECT #
##################

GARMIN_CONNECT_USERNAME = get_env_variable("GARMIN_CONNECT_USERNAME", "")
GARMIN_CONNECT_PASSWORD = get_env_variable("GARMIN_CONNECT_PASSWORD", "")
GARMIN_ACTIVITY_URL = get_env_variable("GARMIN_ACTIVITY_URL", "")

#################
# ELEVATION API #
#################

# https://elevation-api.io/

ELEVATION_API_KEY = get_env_variable("ELEVATION_API_KEY", "")
ELEVATION_API_RESOLUTION = get_env_variable("ELEVATION_API_RESOLUTION", "")

# https://developers.google.com/maps/documentation/elevation/overview

GOOGLE_API_KEY = get_env_variable("GOOGLE_API_KEY", "")

