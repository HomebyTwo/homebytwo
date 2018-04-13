from glob import glob
from os import environ, path, sep


def import_env_vars(directory):
    """
    List the files present in the given directory and for each of them create
    an environment variable named after the file, and which value is the
    contents of the file.
    """
    env_vars = glob(path.join(directory, '*'))
    for env_var in env_vars:
        with open(env_var, 'r') as env_var_file:
            environ.setdefault(env_var.split(sep)[-1],
                               env_var_file.read().strip())


def get_project_root_path(*dirs):
    """
    Return the absolute path to the root of the project.
    """
    base_dir = path.join(path.dirname(__file__), '..')
    return path.abspath(path.join(base_dir, *dirs))
