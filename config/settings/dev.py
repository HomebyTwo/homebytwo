from . import get_env_variable
from .base import *  # NOQA


DEBUG = bool(get_env_variable("DEBUG", True))
DEBUG_TOOLBAR_CONFIG = {"INTERCEPT_REDIRECTS": False}
SECRET_KEY = "notverymuchsecret"

INSTALLED_APPS += (
    "debug_toolbar",
    "django_extensions",
)

MIDDLEWARE += ("debug_toolbar.middleware.DebugToolbarMiddleware",)

INTERNAL_IPS = ("127.0.0.1", "10.10.10.10")
