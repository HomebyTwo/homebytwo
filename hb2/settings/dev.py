from . import get_env_variable
from .base import *  # NOQA


DEBUG = bool(get_env_variable('DEBUG', True))
DEBUG_TOOLBAR_CONFIG = {"INTERCEPT_REDIRECTS": False}
MIDDLEWARE_CLASSES += (
    'debug_toolbar.middleware.DebugToolbarMiddleware',
)

SECRET_KEY = 'notverymuchsecret'

INSTALLED_APPS += (
    'debug_toolbar',
    'django_extensions',
)
