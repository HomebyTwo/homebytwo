from django.core.exceptions import ImproperlyConfigured

from pytest import raises

from homebytwo.routes.models import Athlete
from homebytwo.routes.tasks import report_usage_to_coda
from homebytwo.routes.tests.factories import ActivityFactory, RouteFactory
from homebytwo.utils.factories import AthleteFactory


def test_report_usage_to_coda_no_key(settings):
    settings.CODA_API_KEY = None
    assert report_usage_to_coda() == "CODA_API_KEY is not set."


def test_report_usage_to_coda_success(
    athlete, mock_call_json_responses, coda, settings
):

    athletes = AthleteFactory.create_batch(5)
    for athlete in athletes:
        RouteFactory.create_batch(5, athlete=athlete)
        ActivityFactory.create_batch(5, athlete=athlete)

    response_mocks = [
        {
            "url": coda["doc_url"],
            "response_json": "coda_doc.json",
        },
        {
            "url": coda["table_url"],
            "response_json": "coda_table.json",
        },
        {
            "url": coda["table_url"] + "/columns",
            "response_json": "coda_columns.json",
        },
        {
            "url": coda["table_url"] + "/rows",
            "method": "post",
            "response_json": "coda_request.json",
            "status": 202,
        },
    ]

    response = mock_call_json_responses(report_usage_to_coda, response_mocks)
    assert response == "Updated {} rows in Coda table at https://coda.io/d/{}".format(
        Athlete.objects.count(), settings.CODA_DOC_ID
    )


def test_report_usage_to_coda_failure(athlete, mock_call_json_responses, coda):
    RouteFactory(athlete=athlete)
    ActivityFactory(athlete=athlete)
    response_mocks = [
        {
            "url": coda["doc_url"],
            "response_json": "coda_doc.json",
        },
        {
            "url": coda["table_url"],
            "response_json": "coda_table.json",
        },
        {
            "url": coda["table_url"] + "/columns",
            "response_json": "coda_missing_columns.json",
        },
    ]
    with raises(ImproperlyConfigured):
        mock_call_json_responses(report_usage_to_coda, response_mocks)
