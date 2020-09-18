#!/usr/bin/env python
import sys
from os import environ
from pathlib import Path

from config import get_project_root_path, import_env_vars

if __name__ == "__main__":
    import_env_vars(Path(get_project_root_path(), "envdir"))

    environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
