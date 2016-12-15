from .base import *  # NOQA
from . import get_env_variable


###########################
# Force Mailchimp API Key #
###########################

MAILCHIMP_API_KEY = get_env_variable('MAILCHIMP_API_KEY')
MAILCHIMP_LIST_ID = get_env_variable('MAILCHIMP_LIST_ID')