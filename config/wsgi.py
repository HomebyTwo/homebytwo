from os import environ
from pathlib import Path

from django.core.wsgi import get_wsgi_application

from config import get_project_root_path, import_env_vars

import_env_vars(Path(get_project_root_path(), "envdir"))

environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")

application = get_wsgi_application()
