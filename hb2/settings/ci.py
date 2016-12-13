from .base import *  # NOQA
import os

SECRET_KEY = 'SecretKeyForUseOnTravis'
DEBUG = False
TEMPLATE_DEBUG = True

if os.getenv('TRAVIS', None):
    DATABASE_URL = 'postgres://postgres@localhost/travisdb'
