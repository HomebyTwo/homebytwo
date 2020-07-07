import os
import random
from datetime import datetime
from io import StringIO
from pathlib import Path

import dj_database_url
from config import get_project_root_path
from fabric.api import (
    cd,
    env,
    execute,
    get,
    local,
    put,
    require,
    run,
    settings,
    shell_env,
    sudo,
    task,
)
from fabric.context_managers import quiet
from fabric.operations import prompt
from gitric import api as gitric

# This is the definition of your environments. Every item of the ENVIRONMENTS
# dict will be made available as a fabric task and the properties you put in a
# particular environment will be made available in the `env` variable.
ENVIRONMENTS = {
    "prod": {
        "root": "/var/www/homebytwo.ch/",
        "hosts": ["homebytwo@homebytwo.ch"],
        "services_to_restart": ["celeryd", "celerybeat", "gunicorn"],
        # You can set settings that will be automatically deployed when running
        # the `bootstrap` command
        "settings": {
            "CELERY_BROKER_URL": "amqp://localhost",
            "MEDIA_ROOT": "/var/www/homebytwo.ch/media",
            "MEDIA_URL": "/media/",
            "STATIC_ROOT": "/var/www/homebytwo.ch/static",
            "STATIC_URL": "/static/",
        },
    },
    "staging": {
        "root": "/var/www/staging.homebytwo.ch/",
        "hosts": ["homebytwo@staging.homebytwo.ch"],
        "services_to_restart": ["celeryd", "celerybeat", "gunicorn"],
        # You can set settings that will be automatically deployed when running
        # the `bootstrap` command
        "settings": {
            "CELERY_BROKER_URL": "amqp://localhost",
            "MEDIA_ROOT": "/var/www/staging.homebytwo.ch/media",
            "MEDIA_URL": "/media/",
            "STATIC_ROOT": "/var/www/staging.homebytwo.ch/static",
            "STATIC_URL": "/static/",
        },
    },
}

env.project_name = "homebytwo"


def ls(path):
    """
    Return the list of the files in the given directory, omitting . and ...
    """
    with cd(path), quiet():
        files = run("for i in *; do echo $i; done")
        files_list = files.replace("\r", "").split("\n")

    return files_list


def git_push(commit):
    """
    Push the current tree to the remote server and reset the remote git
    repository to the given commit. The commit can be any git object, be it a
    hash, a tag or a branch.
    """
    gitric.force_push()
    gitric.git_seed(get_project_root(), commit)
    gitric.git_reset(get_project_root(), "master")


def get_project_root():
    """
    Return the path to the root of the project on the remote server.
    """
    return Path(env.root, env.project_name).resolve().as_posix()


def get_virtualenv_root():
    """
    Return the path to the virtual environment on the remote server.
    """
    return Path(env.root, "venv").as_posix()


def get_backups_root():
    """
    Return the path to the backups directory on the remote server.
    """
    return Path(env.root, "backups").as_posix()


def run_in_virtualenv(cmd, args):
    """
    Run the given command from the remote virtualenv.
    """
    return run("%s %s" % (Path(get_virtualenv_root(), "bin", cmd).as_posix(), args))


def run_pip(args):
    """
    Run the pip command in the remote virtualenv.
    """
    return run_in_virtualenv("pip", args)


def run_python(args):
    """
    Run the python command in the remote virtualenv.
    """
    return run_in_virtualenv("python", args)


def install_requirements():
    """
    Install the requirements from the base.txt file to the remote virtualenv.
    """
    with cd(get_project_root()):
        run_pip("install -r requirements/base.txt")


def migrate_database():
    with cd(get_project_root()):
        run_python("manage.py migrate")


def collect_static():
    """
    Collect static files to the STATIC_ROOT directory.
    """
    with cd(get_project_root()):
        run_python("manage.py collectstatic --noinput")


def restart_processes():
    """
    Restart processes on the remote server
    """
    for service in env.services_to_restart:
        sudo("/bin/systemctl restart {}.service".format(service), shell=False)


def generate_secret_key():
    """
    Generate a random secret key, suitable to be used as a SECRET_KEY setting.
    """
    return "".join(
        [
            random.SystemRandom().choice(
                "abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)"
            )
            for i in range(50)
        ]
    )


def create_structure():
    """
    Create the basic directory structure on the remote server.
    """
    run("mkdir -p %s" % env.root)

    with cd(env.root):
        run("mkdir -p static backups")
        run("python3 -m venv venv")


@task
def sync_settings():
    """
    Copy all settings defined in the environment to the server.
    """
    for setting, value in env.settings.items():
        set_setting(setting, value=value)


def set_setting(setting_key, value=None, description=None):
    """
    Sets the given setting to the given value on the remote server. If the
    value is not provided, the user will be prompted for it.

    TODO: use the description parameter to display a help text.
    """
    if value is None:
        value = prompt("Please provide value for setting %s: " % setting_key)

    with cd(Path(get_project_root(), "envdir")):
        put(StringIO(value), setting_key)


@task
def bootstrap():
    """
    Deploy the project for the first time. This will create the directory
    structure, push the project and set the basic settings.

    This task needs to be called alongside an environment task, eg. ``fab prod
    bootstrap``.
    """
    create_structure()

    execute(git_push, commit="master")

    required_settings = set(
        ["CELERY_BROKER_URL", "MEDIA_ROOT", "MEDIA_URL", "STATIC_ROOT", "STATIC_URL"]
    )

    env_settings = getattr(env, "settings", {})
    for setting, value in env_settings.items():
        set_setting(setting, value=value)

    # Ask for settings that are required but were not set in the parameters
    # file
    for setting in required_settings - set(env_settings.keys()):
        set_setting(setting)

    set_setting("DJANGO_SETTINGS_MODULE", value="config.settings.prod")
    set_setting("SECRET_KEY", value=generate_secret_key())

    execute(install_requirements)
    execute(collect_static)
    execute(migrate_database)

    execute(restart_processes)


@task
def compile_assets():
    local("npm install")
    local("npm run build")
    local(
        "rsync -e 'ssh -p {port}' -r --exclude *.map --exclude *.swp static/dist/ "
        "{user}@{host}:{path}".format(
            host=env.host, user=env.user, port=env.port, path=Path(env.root, "static"),
        )
    )


@task
def deploy(tag):
    require("root", "project_name")

    execute(git_push, commit="@")
    dump_db(get_backups_root())
    execute(install_requirements)
    execute(collect_static)
    execute(migrate_database)

    execute(restart_processes)
    execute(clean_old_database_backups, nb_backups_to_keep=10)


def dump_db(destination):
    """
    Dump the database to the given directory and return the path to the file created.
    This creates a gzipped SQL file.
    """
    with cd(get_project_root()), quiet():
        db_credentials = run("cat envdir/DATABASE_URL")
    db_credentials_dict = dj_database_url.parse(db_credentials)

    if not is_supported_db_engine(db_credentials_dict["ENGINE"]):
        raise NotImplementedError(
            "The dump_db task doesn't support the remote database engine"
        )

    outfile = Path(
        destination, datetime.now().strftime("%Y-%m-%d_%H%M%S.sql.gz")
    ).as_posix()

    with shell_env(PGPASSWORD=db_credentials_dict["PASSWORD"].replace("$", "\$")):
        run(
            "pg_dump -O -x -h {host} -U {user} {db}|gzip > {outfile}".format(
                host=db_credentials_dict["HOST"],
                user=db_credentials_dict["USER"],
                db=db_credentials_dict["NAME"],
                outfile=outfile,
            )
        )

    return outfile


@task
def fetch_db(destination="."):
    """
    Dump the database on the remote host and retrieve it locally.

    The destination parameter controls where the dump should be stored locally.
    """
    require("root")

    dump_path = dump_db("~")
    get(dump_path, destination)
    run("rm %s" % dump_path)

    return Path(dump_path).name


@task
def import_db(dump_file=None):
    """
    Restore the given database dump.

    The dump must be a gzipped SQL dump. If the dump_file parameter is not set,
    the database will be dumped and retrieved from the remote host.
    """
    with open("envdir/DATABASE_URL", "r") as db_credentials_file:
        db_credentials = db_credentials_file.read()
    db_credentials_dict = dj_database_url.parse(db_credentials)

    if not is_supported_db_engine(db_credentials_dict["ENGINE"]):
        raise NotImplementedError(
            "The import_db task doesn't support your database engine"
        )

    if dump_file is None:
        dump_file = fetch_db()

    db_info = {
        "host": db_credentials_dict["HOST"],
        "user": db_credentials_dict["USER"],
        "db": db_credentials_dict["NAME"],
        "db_dump": dump_file,
    }

    with shell_env(PGPASSWORD=db_credentials_dict["PASSWORD"]):
        with settings(warn_only=True):
            local("dropdb -h {host} -U {user} {db}".format(**db_info))

        local("createdb -h {host} -U {user} {db}".format(**db_info))
        local("gunzip -c {db_dump}|psql -h {host} -U {user} {db}".format(**db_info))


@task
def clean_old_database_backups(nb_backups_to_keep):
    """
    Remove old database backups from the system and keep `nb_backups_to_keep`.
    """
    backups = ls(get_backups_root())
    backups = sorted(backups, reverse=True)

    if len(backups) > nb_backups_to_keep:
        backups_to_delete = backups[nb_backups_to_keep:]

        for backup_to_delete in backups_to_delete:
            run('rm "%s"' % Path(get_backups_root(), backup_to_delete))

        print("%d backups deleted." % len(backups_to_delete))
    else:
        print("No backups to delete.")


@task
def fetch_media():
    """
    sync local media folder with remote data
    """
    # absolute media root on remote environement
    with cd(get_project_root()), quiet():
        remote_media_root = run("cat envdir/MEDIA_ROOT")

    if Path("envdir/MEDIA_ROOT").exists():
        with open("envdir/MEDIA_ROOT", "r") as media_root_file:
            local_media_root = media_root_file.read()
    else:
        local_media_root = get_project_root_path("homebytwo/media")

    local(
        "rsync -e 'ssh -p {port}' -rv "
        "{user}@{host}:{source_directory} {target_directory}".format(
            user=env.user,
            host=env.host,
            port=env.port,
            source_directory=f"{remote_media_root}{os.sep}",  # add trailing slash
            target_directory=local_media_root,
        )
    )


def is_supported_db_engine(engine):
    return engine in (
        "django.db.backends.postgresql_psycopg2",
        "django.contrib.gis.db.backends.postgis",
    )


# Environment handling stuff
############################


def get_environment_func(key, value):
    def load_environment():
        env.update(value)
        env.environment = key

    load_environment.__name__ = key
    load_environment.__doc__ = "Definition of the %s environment." % key

    return load_environment


def load_environments(environments):
    for (key, values) in environments.items():
        globals()[key] = task(get_environment_func(key, values))


load_environments(ENVIRONMENTS)
