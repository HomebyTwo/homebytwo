from os import environ
from pathlib import Path


def import_env_vars(directory):
    """
    List the files present in the given directory and for each of them create
    an environment variable named after the file, and which value is the
    contents of the file.
    """
    path = Path(directory)
    env_vars = path.glob("*")
    for env_var in env_vars:
        with open(env_var, "r") as env_var_file:
            environ.setdefault(env_var.name, env_var_file.read().strip())


def get_project_root_path(*dirs):
    """
    Return the absolute path to the root of the project.
    """
    base_dir = Path(__file__).resolve().parent / ".."
    return Path(base_dir, *dirs)
