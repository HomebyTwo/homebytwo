import json
from functools import partial
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.shortcuts import resolve_url

import responses
from pytest import fixture
from requests.exceptions import ConnectionError

from .importers.models.switzerlandmobilityroute import parse_route_data
from .utils.factories import AthleteFactory
from .utils.tests import open_data

HTTP_METHODS = {
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
def current_dir_path(request):
    return Path(request.module.__file__).parent.resolve()


@fixture
def open_file(current_dir_path):
    def _open_file(file, binary=False):
        return open_data(file, current_dir_path, binary)

    return _open_file


@fixture
def read_file(open_file):
    def _read_file(file, binary=False):
        return open_file(file, binary=binary).read()

    return _read_file


@fixture
def read_json_file(read_file):
    def _read_json_file(file):
        return json.loads(read_file(file))

    return _read_json_file


@fixture
def uploaded_file(read_file):
    def _uploaded_file(file):
        return SimpleUploadedFile(
            name=file,
            content=read_file(file, binary=True),
        )

    return _uploaded_file


@fixture
def switzerland_mobility_data_from_json(read_json_file):
    def _parse_data(file):
        return parse_route_data(read_json_file(file))

    return _parse_data


@fixture
def mocked_responses():
    with responses.RequestsMock() as response:
        yield response


@fixture
def mock_file_response(mocked_responses, read_file):
    def _mock_file_response(
        url,
        response_file,
        binary=False,
        method="get",
        status=200,
        content_type="text/html; charset=utf-8",
        content_length="0",
        replace=False,
    ):
        kwargs = {
            "method": HTTP_METHODS.get(method),
            "url": url,
            "content_type": content_type,
            "body": read_file(response_file, binary=binary),
            "status": status,
            "headers": {"content-length": content_length},
        }
        if replace:
            mocked_responses.replace(**kwargs)
        else:
            mocked_responses.add(**kwargs)

    return _mock_file_response


@fixture
def mock_html_response(mock_file_response):
    return partial(mock_file_response, content_type="text/html; charset=utf-8")


@fixture
def mock_html_not_found(mock_html_response):
    return partial(mock_html_response, response_file="404.html", status=404)


@fixture
def mock_connection_error(mocked_responses):
    def _mock_connection_error(url):
        mocked_responses.add(
            responses.GET, url, body=ConnectionError("Connection error. ")
        )

    return _mock_connection_error


@fixture
def mock_json_response(mock_file_response):
    return partial(mock_file_response, content_type="application/json")


@fixture
def mock_zip_response(mock_file_response):
    return partial(mock_file_response, content_type="application/zip", binary=True)


@fixture
def mock_strava_streams_response(settings, mock_json_response):
    settings.STRAVA_ROUTE_URL = (
        settings.STRAVA_ROUTE_URL or "https://strava.org/route/%d"
    )

    def _mock_strava_streams_response(
        source_id,
        streams_json="strava_streams_run.json",
        api_streams_status=200,
    ):
        mock_json_response(
            STRAVA_API_BASE_URL + "routes/%d/streams" % source_id,
            response_file=streams_json,
            status=api_streams_status,
        )

    return _mock_strava_streams_response


@fixture
def mock_route_details_responses(
    settings, mock_json_response, mock_strava_streams_response
):
    settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL = (
        settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL
        or "https://switzerland_mobility.org/route/%d/data"
    )
    settings.SWITZERLAND_MOBILITY_ROUTE_URL = (
        settings.SWITZERLAND_MOBILITY_ROUTE_URL
        or "https://switzerland_mobility.org/route/%d"
    )

    def _mock_route_details_responses(
        data_source,
        source_ids,
        api_response_json=None,
        api_response_status=200,
        api_streams_json="strava_streams_run.json",
        api_streams_status=200,
    ):

        # intercept the API call
        api_request_url = {
            "strava": STRAVA_API_BASE_URL + "routes/%d",
            "switzerland_mobility": settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL,
        }
        default_api_response_json = {
            "strava": "strava_route_run.json",
            "switzerland_mobility": "switzerland_mobility_route.json",
        }

        api_response_json = api_response_json or default_api_response_json[data_source]

        for source_id in source_ids:
            mock_json_response(
                url=api_request_url[data_source] % source_id,
                response_file=api_response_json,
                status=api_response_status,
            )

            if data_source == "strava":
                mock_strava_streams_response(
                    source_id, api_streams_json, api_streams_status
                )

    return _mock_route_details_responses


@fixture
def mock_route_details_response(mock_route_details_responses):
    def _mock_route_details_response(data_source, source_id, *args, **kwargs):
        source_ids = [source_id]
        return mock_route_details_responses(data_source, source_ids, *args, **kwargs)

    return _mock_route_details_response


@fixture
def mock_routes_response(settings, mock_json_response):
    def _mock_routes_response(athlete, data_source, response_file=None, status=200):
        response_files = {
            "strava": "strava_route_list.json",
            "switzerland_mobility": "tracks_list.json",
        }
        routes_urls = {
            "strava": (STRAVA_API_BASE_URL + "athletes/%s/routes" % athlete.strava_id),
            "switzerland_mobility": settings.SWITZERLAND_MOBILITY_LIST_URL
            or "https://switzerland_mobility.org/tracks",
        }
        mock_json_response(
            url=routes_urls[data_source],
            response_file=response_file or response_files[data_source],
            method="get",
            status=status,
        )

    return _mock_routes_response


@fixture
def mock_call_response(mocked_responses):
    def _mock_call_response(
        call,
        url,
        body,
        method="get",
        content_type="application/json",
        status=200,
        *args,
        **kwargs,
    ):
        mocked_responses.add(
            method=HTTP_METHODS[method],
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
        call, url, response_file, method="get", status=200, *args, **kwargs
    ):
        return mock_call_response(
            call,
            url,
            body=read_file(response_file),
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
                HTTP_METHODS.get(response.get("method")) or responses.GET,
                response["url"],
                body=read_file(response["response_file"]),
                status=response.get("status") or 200,
                content_type="application/json",
            )
        return call(*args, **kwargs)

    return _mock_call_json_responses


@fixture
def mock_import_route_call_response(client, mock_route_details_response):
    def _mock_import_route_call_response(
        data_source,
        source_id,
        method="get",
        post_data=None,
        follow_redirect=False,
        **kwargs,
    ):

        mock_route_details_response(
            data_source,
            source_id,
            **kwargs,
        )

        # call import_route url
        url = resolve_url("import_route", data_source=data_source, source_id=source_id)
        if method == "get":
            return client.get(url, follow=follow_redirect)
        if method == "post":
            return client.post(url, post_data, follow=follow_redirect)

    return _mock_import_route_call_response


@fixture
def mock_call_connection_error(mock_call_response):
    return partial(mock_call_response, body=ConnectionError("Connection error."))


@fixture
def mock_call_server_error(mock_call_json_response):
    return partial(mock_call_json_response, status=500)


@fixture
def mock_call_not_found(mock_call_json_response):
    return partial(mock_call_json_response, response_file="404.json", status=404)
