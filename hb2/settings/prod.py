from .base import *  # NOQA
from . import get_env_variable


###########################
# Force Mailchimp API Key #
###########################

MAILCHIMP_API_KEY = get_env_variable('MAILCHIMP_API_KEY')
MAILCHIMP_LIST_ID = get_env_variable('MAILCHIMP_LIST_ID')

#######################################
# Force Switzerland Mobility Settings #
#######################################

SWITZERLAND_MOBILITY_LIST_URL = get_env_variable('SWITZERLAND_MOBILITY_LIST_URL')
SWITZERLAND_MOBILITY_LOGIN_URL = get_env_variable('SWITZERLAND_MOBILITY_LOGIN_URL')
SWITZERLAND_MOBILITY_ROUTE_URL = get_env_variable('SWITZERLAND_MOBILITY_ROUTE_URL')
