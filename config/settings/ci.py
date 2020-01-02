from tempfile import TemporaryDirectory

from .base import *  # NOQA

MEDIA_ROOT = TemporaryDirectory().name
SECRET_KEY = 'SecretKeyForUseOnTravis'
DEBUG = False
TEMPLATE_DEBUG = True
