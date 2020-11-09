from os import environ
from pathlib import Path

from celery import Celery

from config import get_project_root_path, import_env_vars

import_env_vars(Path(get_project_root_path(), "envdir"))
environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("homebytwo")

app.config_from_object("django.conf:settings", namespace="celery")
app.autodiscover_tasks()
