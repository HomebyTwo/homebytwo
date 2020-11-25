from io import StringIO

from django.core.management import call_command

import pytest
from pandas import DataFrame

from homebytwo.importers.tests.factories import (
    StravaRouteFactory,
    SwitzerlandMobilityRouteFactory,
)
from homebytwo.routes.tests.factories import ActivityFactory, RouteFactory, \
    ActivityTypeFactory

from ..management.commands.fix_routes_data import interpolate_from_existing_data
from ..models import ActivityType


###################
# fix_routes_data #
###################


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

###################
# fix_routes_data #
###################


would_delete_message = "Would delete {} activities and {} activity_types.\n"
delete_message = "Deleted {} activities and {} activity_types.\n"


def call_cleanup_activity_types(*args, **kwargs):
    out = StringIO()
    call_command(
        "cleanup_activity_types",
        *args,
        stdout=out,
        stderr=StringIO(),
        **kwargs,
    )
    return out.getvalue()


@pytest.fixture
def create_activities():
    """
    create Strava activities for existing activity types so that
    they don't get picked up for deletion
    """
    for activity_type in ActivityType.objects.all():
        ActivityFactory(activity_type=activity_type)


@pytest.mark.django_db
def test_clean_up_activity_types(create_activities):
    assert call_cleanup_activity_types() == delete_message.format(0, 0)


@pytest.mark.django_db
def test_clean_up_activity_types_dry_run(create_activities):
    assert call_cleanup_activity_types("--dry-run") == would_delete_message.format(0, 0)


@pytest.mark.django_db
def test_clean_up_activity_types_unsupported(create_activities):
    ActivityFactory(activity_type=ActivityTypeFactory(name=ActivityType.YOGA))
    assert call_cleanup_activity_types() == delete_message.format(1, 1)


@pytest.mark.django_db
def test_clean_up_activity_types_empty(create_activities):
    ActivityTypeFactory(name=ActivityType.INLINESKATE)
    assert call_cleanup_activity_types("--dry-run") == would_delete_message.format(0, 1)


def call_train_activity_types(*args, **kwargs):
    out = StringIO()
    call_command(
        "train_activity_types",
        *args,
        stdout=out,
        stderr=StringIO(),
        **kwargs,
    )
    return out.getvalue()


trained_message = "{} activity_types trained successfully.\n"


@pytest.mark.django_db
def test_train_activity_types():
    count = ActivityType.objects.count()
    for activity_type in ActivityType.objects.all():
        ActivityFactory(activity_type=activity_type)
    assert trained_message.format(count) in call_train_activity_types()
    for activity_type in ActivityType.objects.all():
        assert not activity_type.model_score == 0.0


@pytest.mark.django_db
def test_train_activity_types_single_activity():
    ActivityFactory(activity_type__name="Run")
    assert trained_message.format(1) in call_train_activity_types("Run")
    assert not ActivityType.objects.get(name="Run").model_score == 0.0


@pytest.mark.django_db
def test_train_activity_types_two_activities():
    ActivityFactory(activity_type__name="Run")
    ActivityFactory(activity_type__name="Ride")
    assert trained_message.format(2) in call_train_activity_types("Run", "Ride")
    assert not ActivityType.objects.get(name="Run").model_score == 0.0
    assert not ActivityType.objects.get(name="Ride").model_score == 0.0


@pytest.mark.django_db
def test_train_activity_types_limit():
    ActivityFactory(activity_type__name="Run")
    assert trained_message.format(1) in call_train_activity_types("Run", "--limit", 1)
    assert not ActivityType.objects.get(name="Run").model_score == 0.0
