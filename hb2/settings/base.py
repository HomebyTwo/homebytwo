import os

import dj_database_url
from . import get_env_variable
from .. import get_project_root_path


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

ALLOWED_HOSTS = tuple(get_env_variable('ALLOWED_HOSTS', '').splitlines())

SECRET_KEY = get_env_variable('SECRET_KEY', '')

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'django.contrib.humanize',
    'djgeojson',
    'leaflet',
    'routes',
    'importers',
    'landingpage',
]

MIDDLEWARE_CLASSES = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'hb2.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'hb2', 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'hb2.context_processor.gtm_context_processor',
            ],
        },
    },
]

WSGI_APPLICATION = 'hb2.wsgi.application'


# Database

DATABASES = {
    "default": dj_database_url.parse(get_env_variable('DATABASE_URL'))
}


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Login Page
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/routes/'

# Internationalization

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Europe/Zurich'

USE_TZ = True


# URL prefix for static files.
STATIC_URL = get_env_variable('STATIC_URL', '/static/')

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# This is usually not used in a dev env, hence the default value
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = get_env_variable('STATIC_ROOT', '/tmp/static')


STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'static'),
)

#############
# Mailchimp #
#############

MAILCHIMP_API_KEY = get_env_variable('MAILCHIMP_API_KEY', '')
MAILCHIMP_LIST_ID = get_env_variable('MAILCHIMP_LIST_ID', '')

######################
# Google Tag Manager #
######################

GTM_CONTAINER_ID = get_env_variable('GTM_CONTAINER_ID', '')

##########
# Mapbox #
##########

# https://www.mapbox.com/studio/account/tokens/

MAPBOX_ACCESS_TOKEN = get_env_variable('MAPBOX_ACCESS_TOKEN', '')


###########
# Leaflet #
###########

# http://krzysztofzuraw.com/blog/2016/geodjango-leaflet-part-two.html

LEAFLET_CONFIG = {
    'DEFAULT_CENTER': (46.818188, 8.227512),
    'DEFAULT_ZOOM': 7,
    'scrollWheelZoom': False,
    'MIN_ZOOM': 3,
    'MAX_ZOOM': 18,
    'TILES': 'https://api.mapbox.com/styles/v1/drixslecta/cipip6crl004wcnngbqlofo9z/tiles/256/{z}/{x}/{y}?access_token=' + MAPBOX_ACCESS_TOKEN,
    'ATTRIBUTION_PREFIX': '<a href="http://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, Imagery &copy; <a href="http://mapbox.com">Mapbox</a>',
    'PLUGINS': {
        'Leaflet.encoded': {
            'js': [STATIC_URL + '/js/Polyline.encoded.js'],
            'auto-include': True,
        },
    }
}


##########
# Strava #
##########

# https://www.strava.com/settings/api

STRAVA_CLIENT_ID = get_env_variable('STRAVA_CLIENT_ID', '')
STRAVA_CLIENT_SECRET = get_env_variable('STRAVA_CLIENT_SECRET', '')


########################
# Switzerland Mobility #
########################

# Login to retrieve user route list from https://map.wanderland.ch/

SWITZERLAND_MOBILITY_USERNAME = get_env_variable('SWITZERLAND_MOBILITY_USERNAME', '')
SWITZERLAND_MOBILITY_PASSWORD = get_env_variable('SWITZERLAND_MOBILITY_PASSWORD', '')


############################
# Google API for elevation #
############################

# https://developers.google.com/maps/documentation/elevation/start

GOOGLEMAPS_API_KEY = get_env_variable('GOOGLEMAPS_API_KEY', '')


##############################
# Swiss public transport API #
##############################

# http://transport.opendata.ch/docs.html

SWISS_PUBLIC_TRANSPORT_API_URL = get_env_variable('SWISS_PUBLIC_TRANSPORT_API_URL', '')
