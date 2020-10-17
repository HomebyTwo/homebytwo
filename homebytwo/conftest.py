from functools import partial
from pathlib import Path
from random import randint

from django.core.files.uploadedfile import SimpleUploadedFile
from django.shortcuts import resolve_url

import responses
from pytest import fixture
from requests.exceptions import ConnectionError

from .importers.elevation_api import (ELEVATION_API_ENDPOINT, MAX_NUMBER_OF_POINTS,
                                      RESOLUTION, chunk)
from .utils.factories import AthleteFactory
from .utils.tests import open_data

METHODS = {
    "get": responses.GET,
    "post": responses.POST,
    "delete": responses.DELETE,
}

STRAVA_API_BASE_URL = "https://www.strava.com/api/v3/"


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
    return Path(request.module.__file__).parent.resolve()


@fixture
def open_file(data_dir_path):
    def _open_file(file, binary=False):
        return open_data(file, data_dir_path, binary)

    return _open_file


@fixture
def read_file(open_file):
    def _read_file(file, binary=False):
        return open_file(file, binary=binary).read()

    return _read_file


@fixture
def celery(settings):
    settings.celery_task_always_eager = True
    settings.celery_task_eager_propagates = True


@fixture
def coda(settings):
    settings.CODA_API_KEY = "coda_key"
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
def uploaded_file(read_file):
    def _uploaded_file(file):
        return SimpleUploadedFile(
            name=file,
            content=read_file(file, binary=True),
        )

    return _uploaded_file


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


@fixture
def add_elevation_response(mocked_responses):
    def _add_elevation_response(elevations, resolution=RESOLUTION):
        mocked_responses.add(
            responses.POST,
            ELEVATION_API_ENDPOINT,
            json={"elevations": elevations, "resolution": resolution},
        )

    return _add_elevation_response


@fixture
def add_elevation_responses(add_elevation_response):
    def _add_elevation_responses(
        number_of_elevations, resolution="30m-interpolated", missing_value=False
    ):
        elevations = [
            {"lat": 0.0, "lon": 0.0, "elevation": x}
            for x in range(number_of_elevations)
        ]
        if missing_value:
            elevations[randint(0, number_of_elevations - 1)]["elevation"] = -9999.0

        for elevations_subset in chunk(elevations, MAX_NUMBER_OF_POINTS):
            add_elevation_response(elevations_subset, resolution=resolution)

    return _add_elevation_responses


@fixture
def import_route_response(mocked_responses, settings, read_file, client):
    def _get_import_route_response(
        data_source,
        source_id,
        api_response_json=None,
        api_response_status=200,
        api_response_content_type="application/json",
        method="get",
        post_data=None,
        follow_redirect=False,
    ):

        # intercept the API call
        api_request_url = {
            "strava": STRAVA_API_BASE_URL + "routes/%d",
            "switzerland_mobility": settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL,
        }
        default_api_response_json = {
            "strava": "strava_route_detail.json",
            "switzerland_mobility": "2191833_show.json",
        }
        api_response_file = api_response_json or default_api_response_json[data_source]

        mocked_responses.add(
            method=responses.GET,
            url=api_request_url[data_source] % source_id,
            content_type=api_response_content_type,
            body=read_file(api_response_file),
            status=api_response_status,
        )

        if data_source == "strava":
            # intercept Strava streams call
            mocked_responses.add(
                responses.GET,
                STRAVA_API_BASE_URL + "routes/%d/streams" % source_id,
                content_type="application/json",
                body=read_file("strava_streams.json"),
                status=200,
            )

        # call import url
        url = resolve_url(
            "import_route", data_source=data_source, source_id=source_id
        )
        if method == "get":
            return client.get(url, follow=follow_redirect)
        if method == "post":
            return client.post(url, post_data, follow=follow_redirect)

    return _get_import_route_response
