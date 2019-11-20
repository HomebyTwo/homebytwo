import os

from celery import Celery
from config import get_project_root_path, import_env_vars

# set env variables from files
import_env_vars(os.path.join(get_project_root_path(), "envdir"))

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("homebytwo")
app.config_from_object("django.conf:settings")
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print("Request: {0!r}".format(self.request))
