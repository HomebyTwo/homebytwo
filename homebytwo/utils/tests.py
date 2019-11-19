import shutil
import tempfile
from os.path import dirname, join, realpath

from django.conf import settings
from django.test.runner import DiscoverRunner


def open_data(file, dir_path, binary=True):
    data_dir = "data"
    path = join(dir_path, data_dir, file,)

    if binary:
        return open(path, "rb")
    else:
        return open(path)


def read_data(file, dir_path=dirname(realpath(__file__)), binary=False):
    return open_data(file, dir_path, binary).read()


def raise_connection_error(self, request, uri, headers):
    """
    raises a connection error to use as the body of the mock
    response in httpretty. Unfortunately httpretty outputs to stdout:
    cf. https://stackoverflow.com/questions/36491664/
    """
    raise ConnectionError("Connection error.")


class TempMediaMixin(object):
    """
    Mixin to create MEDIA_ROOT in temp and tear down when complete.
    https://www.caktusgroup.com/blog/2013/06/26/media-root-and-django-tests/
    """

    def setup_test_environment(self):
        "Create temp directory and update MEDIA_ROOT and default storage."
        super(TempMediaMixin, self).setup_test_environment()
        settings._original_media_root = settings.MEDIA_ROOT
        settings._original_file_storage = settings.DEFAULT_FILE_STORAGE
        self._temp_media = tempfile.mkdtemp()
        settings.MEDIA_ROOT = self._temp_media
        settings.DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"

    def teardown_test_environment(self):
        "Delete temp storage."
        super(TempMediaMixin, self).teardown_test_environment()
        shutil.rmtree(self._temp_media, ignore_errors=True)
        settings.MEDIA_ROOT = settings._original_media_root
        del settings._original_media_root
        settings.DEFAULT_FILE_STORAGE = settings._original_file_storage
        del settings._original_file_storage


class CustomTestSuiteRunner(TempMediaMixin, DiscoverRunner):
    """
    Local test suite runner.
    """
