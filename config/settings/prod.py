import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration

from . import get_env_variable
from .base import *  # NOQA

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "file": {
            "level": "ERROR",
            "class": "logging.FileHandler",
            "filename": "/var/log/django/{host}.log".format(host=ALLOWED_HOSTS[0]),
        },
    },
    "loggers": {"django": {"handlers": ["file"], "level": "ERROR", "propagate": True}},
}

######################
# Sentry Integration #
######################

sentry_sdk.init(
    dsn="https://98f1c311a2574ef786731e08bd17e712@sentry.io/1823093",
    integrations=[DjangoIntegration(), CeleryIntegration()],
)

###########################
# Force Celery Broker URL #
###########################

CELERY_BROKER_URL = get_env_variable("CELERY_BROKER_URL")

###########################
# Force Mailchimp API Key #
###########################

MAILCHIMP_API_KEY = get_env_variable("MAILCHIMP_API_KEY")
MAILCHIMP_LIST_ID = get_env_variable("MAILCHIMP_LIST_ID")

#######################################
# Force Switzerland Mobility Settings #
#######################################

SWITZERLAND_MOBILITY_LIST_URL = get_env_variable("SWITZERLAND_MOBILITY_LIST_URL")
SWITZERLAND_MOBILITY_LOGIN_URL = get_env_variable("SWITZERLAND_MOBILITY_LOGIN_URL")
SWITZERLAND_MOBILITY_ROUTE_URL = get_env_variable("SWITZERLAND_MOBILITY_ROUTE_URL")
SWITZERLAND_MOBILITY_ROUTE_DATA_URL = get_env_variable(
    "SWITZERLAND_MOBILITY_ROUTE_DATA_URL"
)

#################################
# Force Strava related Settings #
#################################

STRAVA_CLIENT_ID = get_env_variable("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = get_env_variable("STRAVA_CLIENT_SECRET")
STRAVA_ROUTE_URL = get_env_variable("STRAVA_ROUTE_URL")
STRAVA_VERIFY_TOKEN = get_env_variable("STRAVA_VERIFY_TOKEN")

#################################
# Force Mapbox related Settings #
#################################

MAPBOX_ACCESS_TOKEN = get_env_variable("MAPBOX_ACCESS_TOKEN")

#############
# Force GTM #
#############

GTM_CONTAINER_ID = get_env_variable("GTM_CONTAINER_ID")

##################
# Force GARMIN CONNECT #
##################

GARMIN_CONNECT_USERNAME = get_env_variable("GARMIN_CONNECT_USERNAME")
GARMIN_CONNECT_PASSWORD = get_env_variable("GARMIN_CONNECT_PASSWORD")
GARMIN_ACTIVITY_URL = get_env_variable("GARMIN_ACTIVITY_URL")
