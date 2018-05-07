#!/usr/bin/env python
import os
import sys

from config import import_env_vars, get_project_root_path

if __name__ == "__main__":
    import_env_vars(os.path.join(get_project_root_path(), 'envdir'))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
