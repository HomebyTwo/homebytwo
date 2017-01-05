import os

from hb2 import get_project_root_path, import_env_vars

import_env_vars(os.path.join(get_project_root_path(), 'envdir'))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hb2.settings.base")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
