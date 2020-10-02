from functools import partial
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
import httpretty

from pytest import fixture

from .utils.factories import AthleteFactory
from .utils.tests import open_data, raise_connection_error


@fixture(autouse=True)
def media_storage(settings, tmpdir):
    settings.MEDIA_ROOT = tmpdir.strpath


@fixture()
def celery(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@fixture()
def athlete(db, client):
    athlete = AthleteFactory(user__password="test_password")
    client.login(username=athlete.user.username, password="test_password")
    return athlete


@fixture()
def test_dir_path(request):
    def _test_dir_path():
        return Path(request.module.__file__).parent.resolve()

    return _test_dir_path


@fixture()
def open_file(test_dir_path):
    def _open_file(file, binary=False):
        return open_data(file, test_dir_path(), binary)

    return _open_file


@fixture()
def read_file(open_file):
    def _read_file(file, binary=False):
        return open_file(file, binary=binary).read()

    return _read_file


@fixture()
def enable_httpretty():
    def _httpretty(
        call,
        uri,
        method="get",
        body=None,
        content_type="application/json",
        status=200,
        *args,
        **kwargs
    ):
        with httpretty.enabled(allow_net_connect=False):
            method_map = {
                "get": httpretty.GET,
                "post": httpretty.POST,
                "delete": httpretty.DELETE,
            }
            httpretty.register_uri(
                method=method_map[method],
                uri=uri,
                body=body,
                content_type=content_type,
                status=status,
            )
            return call(*args, **kwargs)

    return _httpretty


@fixture()
def uploaded_file(read_file):
    def _uploaded_file(file):
        return SimpleUploadedFile(
            name=file,
            content=read_file(file, binary=True),
        )

    return _uploaded_file


@fixture()
def intercept(read_file, enable_httpretty):
    def _intercept(call, url, response_json, method="get", status=200, *args, **kwargs):
        return enable_httpretty(
            call,
            url,
            body=read_file(response_json),
            method=method,
            status=status,
            *args,
            **kwargs
        )

    return _intercept


@fixture()
def connection_error(enable_httpretty):
    return partial(enable_httpretty, body=raise_connection_error)


@fixture()
def server_error(intercept):
    return partial(intercept, status=500)


@fixture()
def not_found(intercept):
    return partial(intercept, status=404)
