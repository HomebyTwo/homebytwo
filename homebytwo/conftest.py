from functools import partial
import responses
from pathlib import Path
from pytest import fixture
from requests.exceptions import ConnectionError

from .utils.factories import AthleteFactory
from .utils.tests import open_data

METHODS = {
    "get": responses.GET,
    "post": responses.POST,
    "delete": responses.DELETE,
}


@fixture(autouse=True)
def media_storage(settings, tmpdir):
    settings.MEDIA_ROOT = tmpdir.strpath


@fixture
def athlete(db, client):
    athlete = AthleteFactory(user__password="test_password")
    client.login(username=athlete.user.username, password="test_password")
    return athlete


@fixture
def data_dir_path(request):
    def _data_dir_path():
        return Path(request.module.__file__).parent.resolve()

    return _data_dir_path


@fixture
def open_file(data_dir_path):
    def _open_file(file, binary=False):
        return open_data(file, data_dir_path(), binary)

    return _open_file


@fixture
def read_file(open_file):
    def _read_file(file, binary=False):
        return open_file(file, binary=binary).read()

    return _read_file


@fixture
def celery(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True

@fixture
def coda(settings):
    settings.CODA_DOC_ID = "doc_id"
    settings.CODA_TABLE_ID = "grid-table_id"
    api_url = "https://coda.io/apis/v1"
    doc_url = api_url + f"/docs/{settings.CODA_DOC_ID}/"
    table_url = doc_url + f"tables/{settings.CODA_TABLE_ID}"
    yield {"doc_url": doc_url, "table_url": table_url}


@fixture
def mocked_responses():
    with responses.RequestsMock() as response:
        yield response


@fixture
def mock_call_response(mocked_responses):
    def _mock_call_response(
        call,
        url,
        method="get",
        body=None,
        content_type="application/json",
        status=200,
        *args,
        **kwargs,
    ):
        mocked_responses.add(
            method=METHODS[method],
            url=url,
            body=body,
            content_type=content_type,
            status=status,
        )
        return call(*args, **kwargs)

    return _mock_call_response


@fixture
def mock_call_json_response(read_file, mock_call_response):
    def _mock_call_json_response(
        call, url, response_json, method="get", status=200, *args, **kwargs
    ):

        return mock_call_response(
            call,
            url,
            body=read_file(response_json),
            method=method,
            status=status,
            *args,
            **kwargs,
        )

    return _mock_call_json_response


@fixture
def mock_call_json_responses(read_file, mocked_responses):
    def _mock_call_json_responses(call, response_mocks, *args, **kwargs):
        for response in response_mocks:
            mocked_responses.add(
                METHODS.get(response.get("method")) or responses.GET,
                response["url"],
                body=read_file(response["response_json"]),
                status=response.get("status") or 200,
                content_type="application/json",
            )
        return call(*args, **kwargs)

    return _mock_call_json_responses


@fixture
def connection_error(mock_call_response):
    return partial(mock_call_response, body=ConnectionError("Connection error."))


@fixture
def server_error(mock_call_json_response):
    return partial(mock_call_json_response, status=500)


@fixture
def not_found(mock_call_json_response):
    return partial(mock_call_json_response, status=404)
