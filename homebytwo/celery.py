from os import environ
from pathlib import Path

from django.apps import AppConfig, apps
from django.conf import settings

from celery import Celery

from config import get_project_root_path, import_env_vars

if not settings.configured:
    import_env_vars(Path(get_project_root_path(), "envdir"))
    environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("homebytwo")


class CeleryConfig(AppConfig):
    name = "homebytwo.celery"
    verbose_name = "Celery config for homebytwo"

    def ready(self):
        app.config_from_object("django.conf:settings", namespace="CELERY")
        installed_apps = [app_config.name for app_config in apps.get_app_configs()]
        app.autodiscover_tasks(lambda: installed_apps, force=True)
