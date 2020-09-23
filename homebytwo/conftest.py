from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile

from pytest import fixture

from .utils.factories import AthleteFactory
from .utils.tests import open_data


@fixture(autouse=True)
def media_storage(settings, tmpdir):
    settings.MEDIA_ROOT = tmpdir.strpath


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
def uploaded_file(read_file):
    def _uploaded_file(file):
        return SimpleUploadedFile(
            name=file,
            content=read_file(file, binary=True),
        )

    return _uploaded_file
