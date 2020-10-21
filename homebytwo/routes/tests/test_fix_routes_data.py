from io import StringIO

import responses
from django.core.management import call_command

import pytest
from pandas import DataFrame

from homebytwo.conftest import STRAVA_API_BASE_URL
from homebytwo.importers.tests.factories import (
    StravaRouteFactory,
    SwitzerlandMobilityRouteFactory,
)
from homebytwo.routes.management.commands.fix_routes_data import (
    interpolate_from_existing_data,
)
from homebytwo.routes.tests.factories import RouteFactory


def call_fix_command(*args, **kwargs):
    out = StringIO()
    call_command(
        "fix_routes_data",
        *args,
        stdout=out,
        stderr=StringIO(),
        **kwargs,
    )
    return out.getvalue()


def test_interpolate_from_existing():
    route = RouteFactory.build()
    route.data.drop(index=list(range(10)), inplace=True)
    assert not len(route.geom) == len(route.data.altitude)
    assert interpolate_from_existing_data(route)
    assert len(route.geom) == len(route.data.altitude)


@pytest.mark.django_db
def test_fix_routes_data_no_routes():
    out = call_fix_command("--verbosity", "2")
    assert "Re-imported 0 routes and restored 0 from data." in out


@pytest.mark.django_db
def test_fix_routes_data_all(
    settings,
    mock_route_details_response,
    mock_strava_streams_response,
):
    settings.SWITZERLAND_MOBILITY_ROUTE_DATA_URL = "https://example.org/%d"

    RouteFactory()

    bad_data = DataFrame({"distance": range(10), "altitude": range(10)})

    strava_route = StravaRouteFactory(data=bad_data)
    mock_strava_streams_response(strava_route.source_id)

    switzerland_mobility_route = SwitzerlandMobilityRouteFactory(data=bad_data)
    mock_route_details_response(
        data_source=switzerland_mobility_route.data_source,
        source_id=switzerland_mobility_route.source_id,
        api_response_status=404,
        api_response_json="404.json",
    )

    out = call_fix_command("--verbosity", "2")
    assert "Re-imported 1 routes and restored 1 from data." in out
