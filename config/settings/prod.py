from .base import *  # NOQA
from . import get_env_variable


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "file": {
            "level": "ERROR",
            "class": "logging.FileHandler",
            "filename": "/var/log/django.log",
        },
    },
    "loggers": {
        "django": {"handlers": ["file"], "level": "ERROR", "propagate": True,},
    },
}

###########################
# Force Celery Broker URL #
###########################

CELERY_BROKER_URL = get_env_variable('CELERY_BROKER_URL')

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
STRAVA_VERIFY_TOKEN = get_env_variable("STRAVA_VERIFY_TOKEN")
STRAVA_ROUTE_URL = get_env_variable("STRAVA_ROUTE_URL")

#################################
# Force Mapbox related Settings #
#################################

MAPBOX_ACCESS_TOKEN = get_env_variable("MAPBOX_ACCESS_TOKEN")
