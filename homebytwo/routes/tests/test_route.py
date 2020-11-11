from datetime import timedelta
from os import urandom
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib.gis.geos import LineString, Point
from django.contrib.gis.measure import Distance
from django.core.management import CommandError, call_command
from django.forms.models import model_to_dict
from django.shortcuts import resolve_url
from django.urls import resolve, reverse
from django.utils.six import StringIO

import pytest
from pandas import DataFrame
from pytest_django.asserts import assertContains, assertRedirects

from ...utils.factories import AthleteFactory
from ...utils.tests import create_checkpoints_from_geom, create_route_with_checkpoints
from ..fields import DataFrameField
from ..forms import RouteForm
from ..models import Route
from ..templatetags.duration import base_round, display_timedelta, nice_repr
from .factories import ActivityPerformanceFactory, PlaceFactory, RouteFactory

###############
# model Route #
###############


def test_str():
    route = RouteFactory.build()
    assert str(route) == "{activity_type}: {name}".format(
        activity_type=str(route.activity_type), name=route.name
    )


def test_display_url(athlete):
    route = RouteFactory(athlete=athlete)
    assert route.display_url == route.get_absolute_url()

    match = resolve(route.edit_url)
    assert match.app_name == "routes"
    assert match.url_name == "edit"

    match = resolve(route.update_url)
    assert match.app_name == "routes"
    assert match.url_name == "update"

    match = resolve(route.delete_url)
    assert match.app_name == "routes"
    assert match.url_name == "delete"

    match = resolve(route.gpx_url)
    assert match.app_name == "routes"
    assert match.url_name == "gpx"

    match = resolve(route.import_url)
    assert match.url_name == "import_route"


def test_get_total_distance():
    route = RouteFactory.build(total_distance=12345)
    total_distance = route.get_total_distance()

    assert isinstance(total_distance, Distance)
    assert total_distance.km == 12.345


def test_get_total_elevation_gain():
    route = RouteFactory.build(total_elevation_gain=1234)
    total_elevation_gain = route.get_total_elevation_gain()

    assert isinstance(total_elevation_gain, Distance)
    assert total_elevation_gain.ft == pytest.approx(4048.556430446194)


def test_get_total_elevation_loss():
    route = RouteFactory.build(total_elevation_loss=4321)
    total_elevation_loss = route.get_total_elevation_loss()

    assert isinstance(total_elevation_loss, Distance)
    assert total_elevation_loss.m == 4321


def test_get_start_altitude():
    data = DataFrame(
        [[0, 0], [1234, 1000]],
        columns=["altitude", "distance"],
    )
    route = RouteFactory.build(
        data=data,
        total_distance=1000,
        geom=LineString(
            ((500000.0, 300000.0), (501000.0, 300000.0)), srid=21781
        ).transform(3857, clone=True),
    )
    start_altitude = route.get_start_altitude()
    end_altitude = route.get_end_altitude()

    assert start_altitude.m == 0
    assert end_altitude.m == 1234


def test_get_distance_data():
    data = DataFrame(
        [[0, 0], [1000, 1000]],
        columns=["altitude", "distance"],
    )
    route = RouteFactory.build(data=data, total_distance=1000)

    # make the call
    point_altitude = route.get_distance_data(0.5, "altitude")

    assert isinstance(point_altitude, Distance)
    assert point_altitude.m == 500


def test_get_start_and_end_places(athlete):
    route = RouteFactory.build(athlete=athlete)

    route.start_place.name = "Start Place"
    route.start_place.save()
    route.end_place.name = "End Place"
    route.end_place.save()

    start_place = route.get_closest_places_along_line()[0]
    end_place = route.get_closest_places_along_line(1)[0]

    assert start_place.distance_from_line.m == 0
    assert start_place.name == "Start Place"
    assert end_place.distance_from_line.m == 0
    assert end_place.name == "End Place"


def test_source_link(athlete, settings):
    settings.SWITZERLAND_MOBILITY_ROUTE_URL = (
        "https://switzerland_mobility_route_url/%d"
    )
    settings.STRAVA_ROUTE_URL = "https://strava_route_url/%d"

    route = RouteFactory(data_source="strava", source_id=777)
    source_url = "https://strava_route_url/777"
    assert route.source_link.url == source_url
    assert route.source_link.text == "Strava"

    route = RouteFactory(data_source="switzerland_mobility", source_id=777)
    source_url = "https://switzerland_mobility_route_url/777"
    assert route.source_link.url == source_url
    assert route.source_link.text == "Switzerland Mobility Plus"

    route = RouteFactory()
    assert route.source_link is None


def test_get_route_details(athlete):
    route = RouteFactory(athlete=athlete)
    with pytest.raises(NotImplementedError):
        route.get_route_details()


def test_get_route_data(athlete):
    route = RouteFactory(athlete=athlete)
    with pytest.raises(NotImplementedError):
        route.get_route_data()


def test_get_or_stub_new(athlete):
    source_id = 123456789
    route, update = Route.get_or_stub(source_id=source_id, athlete=athlete)

    assert route.data_source == "homebytwo"
    assert route.source_id == source_id
    assert route.athlete == athlete
    assert not update
    assert not route.pk


def test_get_or_stub_existing(athlete):
    existing_route = RouteFactory(athlete=athlete)
    retrieved_route, update = Route.get_or_stub(
        source_id=existing_route.source_id, athlete=athlete
    )

    assert retrieved_route.data_source == "homebytwo"
    assert retrieved_route.source_id == existing_route.source_id
    assert retrieved_route.athlete == athlete
    assert update
    assert retrieved_route.pk


def test_find_additional_places(athlete, switzerland_mobility_data_from_json):
    geom, data = switzerland_mobility_data_from_json("2191833_show.json")
    route = RouteFactory(name="Haute-Cime", athlete=athlete, geom=geom, data=data)

    PlaceFactory(
        name="Sur Frête",
        geom=Point(x=778472.6635249017, y=5806086.097085138, srid=3857),
    )
    PlaceFactory(
        name="Col du Jorat",
        geom=Point(x=777622.1292536028, y=5804465.781388815, srid=3857),
    )
    PlaceFactory(
        name="Haute Cime",
        geom=Point(x=770692.9180045408, y=5806199.473715298, srid=3857),
    )
    PlaceFactory(
        name="Col des Paresseux",
        geom=Point(x=770730.0014088114, y=5805770.126578271, srid=3857),
    )
    PlaceFactory(
        name="Col de Susanfe",
        geom=Point(x=770355.7793282912, y=5804143.91778818, srid=3857),
    )

    checkpoints = route.find_possible_checkpoints(max_distance=100)
    checkpoint_names = [checkpoint.place.name for checkpoint in checkpoints]

    assert len(checkpoints) == 6
    assert checkpoint_names.count("Col des Paresseux") == 2
    assert "Haute Cime" in [checkpoint.place.name for checkpoint in checkpoints]
    assert route.start_place.name not in checkpoint_names
    assert route.end_place.name not in checkpoint_names


def test_calculate_step_distances():
    data = DataFrame(
        {
            "altitude": [0, 1, 2, 1, 0],
            "distance": [0, 1, 2, 3, 4],
        }
    )
    geom = LineString((0, 0), (0, 1), (0, 2), (0, 3), (0, 4))
    route = RouteFactory.build(data=data, geom=geom)
    route.calculate_step_distances(min_distance=1, commit=False)

    assert route.data.columns.to_list() == ["altitude", "distance", "step_distance"]
    step_distance = [0.0, 1.0, 1.0, 1.0, 1.0]
    assert route.data.step_distance.to_list() == step_distance


def test_calculate_step_distances_bad_values():
    data = DataFrame(
        {
            "altitude": [0, 1, 2, 1, 0],
            "distance": [0, 0.5, 1, 2, 3],
        }
    )
    geom = LineString([(lng, 0) for lng in data.distance.to_list()])
    route = RouteFactory.build(data=data, geom=geom)
    route.calculate_step_distances(min_distance=1, commit=False)

    step_distance = [0.0, 2.0, 1.0]
    assert route.data.step_distance.to_list() == step_distance
    assert len(route.data.step_distance) == len(route.geom)


def test_calculate_step_distances_commit(athlete):
    data = DataFrame(
        {
            "altitude": [0, 1, 2, 1, 0],
            "distance": [0, 1, 2, 3, 4],
        }
    )
    geom = LineString([(lng, 0) for lng in data.distance.to_list()])
    route = RouteFactory(name="step_distance", data=data, geom=geom, athlete=athlete)
    route.calculate_step_distances(min_distance=1, commit=True)

    saved_route = Route.objects.get(name="step_distance", athlete=athlete)

    step_distance = [0.0, 1.0, 1.0, 1.0, 1.0]
    assert saved_route.data.step_distance.to_list() == step_distance
    assert len(saved_route.data.step_distance) == len(saved_route.geom)


def test_calculate_distances_impossible():
    data = DataFrame(
        {
            "altitude": [0, 1, 2, 1, 0],
            "distance": [0, 0.5, 1, 1.5, 2],
        }
    )
    geom = LineString([(lng, 0) for lng in data.distance.to_list()])
    route = RouteFactory.build(data=data, geom=geom)
    with pytest.raises(ValueError):
        route.calculate_step_distances(min_distance=1, commit=False)


def test_calculate_gradients():
    data = DataFrame(
        {
            "altitude": [0, 1, 2, 3, 2, 1, 0],
            "distance": [0, 1, 2, 3, 4, 5, 6],
        }
    )
    geom = LineString((0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (0, 6))
    route = RouteFactory.build(data=data, geom=geom)
    route.calculate_gradients(max_gradient=100, commit=False)

    assert route.data.columns.to_list() == ["altitude", "distance", "gradient"]
    gradients = [0.0, 100.0, 100.0, 100.0, -100.0, -100.0, -100.0]
    assert route.data.gradient.to_list() == gradients


def test_calculate_gradients_bad_values():
    geom = LineString((0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (0, 6))
    data = DataFrame(
        {
            "altitude": [0, 1, 3, 3, 1, 1, 0],
            "distance": [0, 1, 2, 3, 4, 5, 6],
        }
    )
    route = RouteFactory.build(data=data, geom=geom)
    route.calculate_gradients(max_gradient=100, commit=False)

    gradients = [0.0, 100.0, 100.0, -100.0, -100.0]
    assert route.data.gradient.to_list() == gradients
    assert len(route.data.gradient) == len(route.geom)


def test_calculate_gradients_commit(athlete):
    geom = LineString((0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (0, 6))
    data = DataFrame(
        {
            "altitude": [0, 1, 2, 3, 1, 1, 0],
            "distance": [0, 1, 2, 3, 4, 5, 6],
        }
    )
    route = RouteFactory(name="gradient", data=data, geom=geom, athlete=athlete)
    route.calculate_gradients(max_gradient=100, commit=True)

    gradients = [0.0, 100.0, 100.0, 100.0, -100.0, -100.0]
    saved_route = Route.objects.get(name="gradient", athlete=athlete)
    assert saved_route.data.gradient.to_list() == gradients
    assert len(saved_route.data.gradient) == len(saved_route.geom)


def test_calculate_gradients_impossible():
    geom = LineString((0, 0), (0, 1), (0, 2), (0, 3), (0, 4))
    data = DataFrame(
        {
            "altitude": [0, 2, 4, 6, 10],
            "distance": [0, 1, 2, 3, 4],
        }
    )
    route = RouteFactory.build(data=data, geom=geom)
    with pytest.raises(ValueError):
        route.calculate_gradients(max_gradient=100, commit=False)


def test_add_distance_and_elevation_totals():
    route = RouteFactory.build(total_distance=1000, total_elevation_gain=500)
    route.add_distance_and_elevation_totals(commit=False)
    assert route.data.total_distance.unique() == [route.total_distance]
    assert route.data.total_elevation_gain.unique() == [route.total_elevation_gain]
    assert route.data.columns.to_list() == [
        "altitude",
        "distance",
        "total_distance",
        "total_elevation_gain",
    ]


def test_add_distance_and_elevation_totals_commit(athlete):
    route = RouteFactory(
        name="totals", total_distance=1000, total_elevation_gain=500, athlete=athlete
    )
    route.add_distance_and_elevation_totals(commit=True)

    saved_route = Route.objects.get(name="totals", athlete=athlete)
    assert route.data.columns.to_list() == [
        "altitude",
        "distance",
        "total_distance",
        "total_elevation_gain",
    ]
    assert saved_route.data.total_distance.unique() == [saved_route.total_distance]
    assert saved_route.data.total_elevation_gain.unique() == [
        saved_route.total_elevation_gain
    ]


def test_calculate_cumulative_elevation_differences():
    data = DataFrame(
        {
            "distance": list(range(10)),
            "altitude": [0, 1, 2, 1, 2, 3, 2, 1, 0, 1],
        }
    )
    route = RouteFactory.build(data=data)
    route.calculate_cumulative_elevation_differences(commit=False)
    cumulative_elevation_gain = [0, 1, 2, 2, 3, 4, 4, 4, 4, 5]
    cumulative_elevation_loss = [0, 0, 0, -1, -1, -1, -2, -3, -4, -4]
    assert route.data.columns.to_list() == [
        "distance",
        "altitude",
        "cumulative_elevation_gain",
        "cumulative_elevation_loss",
    ]
    assert route.data.cumulative_elevation_gain.to_list() == cumulative_elevation_gain
    assert route.data.cumulative_elevation_loss.to_list() == cumulative_elevation_loss


def test_calculate_cumulative_elevation_differences_commit(athlete):
    data = DataFrame(
        {
            "distance": list(range(5)),
            "altitude": [0, 1, 2, 1, 0],
        }
    )
    route = RouteFactory(name="cumulative", data=data, athlete=athlete)
    route.calculate_cumulative_elevation_differences(commit=True)

    saved_route = Route.objects.get(name="cumulative", athlete=athlete)
    assert saved_route.data.columns.to_list() == [
        "distance",
        "altitude",
        "cumulative_elevation_gain",
        "cumulative_elevation_loss",
    ]
    assert saved_route.data.cumulative_elevation_gain.to_list() == [0, 1, 2, 2, 2]
    assert saved_route.data.cumulative_elevation_loss.to_list() == [0, 0, 0, -1, -2]


def test_update_permanent_track_data(athlete):
    data = DataFrame(
        {
            "distance": list(range(100)),
            "altitude": list(range(100)),
        }
    )
    geom = LineString([(lng, 0) for lng in data.distance.to_list()])
    route = RouteFactory(name="permanent", athlete=athlete, data=data, geom=geom)
    route.update_permanent_track_data(min_step_distance=1, max_gradient=100)

    saved_route = Route.objects.get(name="permanent", athlete=athlete)

    assert saved_route.data.columns.to_list() == [
        "distance",
        "altitude",
        "step_distance",
        "gradient",
        "cumulative_elevation_gain",
        "cumulative_elevation_loss",
        "total_distance",
        "total_elevation_gain",
    ]

    assert len(saved_route.data.distance) == len(saved_route.geom)


def test_update_permanent_track_data_bad_route():
    data = DataFrame(
        {
            "distance": list(range(10)),
            "altitude": list(range(10)),
        }
    )
    geom = LineString([(lng, 0) for lng in range(20)])
    route = RouteFactory.build(data=data, geom=geom)
    with pytest.raises(ValueError):
        route.update_permanent_track_data(commit=False)


def test_calculate_projected_time_schedule(athlete):
    route = RouteFactory()
    activity_performance = ActivityPerformanceFactory(
        athlete=athlete, activity_type=route.activity_type
    )

    route.calculate_projected_time_schedule(
        user=athlete.user,
        gear=activity_performance.gear_categories[0],
        workout_type=activity_performance.workout_type_categories[-1],
    )

    assert "gear" in route.data.columns and "workout_type" in route.data.columns
    assert "pace" in route.data.columns and "schedule" in route.data.columns


def test_calculate_projected_time_schedule_total_time(athlete):
    route = RouteFactory()

    route.calculate_projected_time_schedule(athlete.user)
    default_total_time = route.get_data(1, "schedule")

    ActivityPerformanceFactory(
        athlete=athlete,
        activity_type=route.activity_type,
        flat_parameter=route.activity_type.flat_parameter / 2,
    )

    route.calculate_projected_time_schedule(athlete.user)
    athlete_total_time = route.get_data(1, "schedule")

    assert default_total_time > athlete_total_time


############################
# template tag duration.py #
############################


def test_schedule_display():
    duration = timedelta(seconds=30, minutes=1, hours=6)
    assert nice_repr(duration) == "6 hours 1 minute 30 seconds"

    duration = timedelta(seconds=0)
    assert nice_repr(duration) == "0 seconds"

    duration = timedelta(seconds=30, minutes=2, hours=2)
    assert nice_repr(duration, display_format="hike") == "2 h 5 min"

    duration = timedelta(seconds=45, minutes=57, hours=2)
    assert nice_repr(duration, display_format="hike") == "3 h"

    duration = timedelta(seconds=30, minutes=2, hours=6)
    assert nice_repr(duration, display_format="hike") == "6 h"

    duration = timedelta(seconds=0, minutes=55, hours=7)
    assert nice_repr(duration, display_format="hike") == "8 h"


def test_display_timedelta():
    assert display_timedelta(None) is None
    assert display_timedelta(0) == "0 seconds"
    with pytest.raises(TypeError):
        display_timedelta("bad_value")


def test_base_round():
    values = [0, 3, 4.85, 12, -7]
    rounded = [base_round(value) for value in values]

    assert rounded == [0, 5, 5, 10, -5]


######################
# view routes:routes #
######################


def test_import_routes_unknown_data_source(athlete, client):
    unknown_data_source_routes_url = reverse(
        "import_routes", kwargs={"data_source": "spam"}
    )
    response = client.get(unknown_data_source_routes_url)
    assert response.status_code == 404


#####################
# view routes:route #
#####################


def test_route_404(athlete, client):
    url = resolve_url("routes:route", pk=0)
    response = client.get(url)
    assert response.status_code == 404


def test_route_edit_404(athlete, client):
    url = resolve_url("routes:edit", pk=0)
    response = client.get(url)
    assert response.status_code == 404


def test_route_delete_404(athlete, client):
    url = resolve_url("routes:delete", pk=0)
    response = client.get(url)
    assert response.status_code == 404


def test_view_route(athlete, client):
    route = RouteFactory(athlete=athlete)
    url = route.get_absolute_url()

    button = '<a class="btn btn--secondary btn--block" href="{href}">{text}</a>'
    edit_button = button.format(
        href=route.get_absolute_url("edit"), text="Add/Remove Checkpoints"
    )
    update_button = button.format(
        href=route.get_absolute_url("update"), text="Re-Import from Source"
    )

    response = client.get(url)
    user = response.context["user"]

    assert user.has_perm(route.get_perm("view"), route)
    assert user.has_perm(route.get_perm("change"), route)

    assertContains(response, route.name)
    assertContains(response, route.start_place.name)
    assertContains(response, route.end_place.name)
    assertContains(response, update_button, html=True)
    assertContains(response, edit_button, html=True)


def test_view_route_success_not_owner(athlete, client):
    route = RouteFactory()
    url = route.get_absolute_url()
    update_url = route.get_absolute_url("update")
    edit_url = route.get_absolute_url("edit")
    response = client.get(url)
    response_content = response.content.decode("UTF-8")

    assert response.status_code == 200
    assert update_url not in response_content
    assert edit_url not in response_content


def test_view_route_success_not_logged_in(athlete, client):
    route = RouteFactory()
    url = route.get_absolute_url()
    update_url = route.get_absolute_url("update")
    edit_url = route.get_absolute_url("edit")
    route_name = route.name

    client.logout()
    response = client.get(url)
    response_content = response.content.decode("UTF-8")

    assertContains(response, route_name)
    assert edit_url not in response_content
    assert update_url not in response_content


def test_view_route_success_no_start_place(athlete, client):
    route = RouteFactory(start_place=None)
    url = route.get_absolute_url()
    route_name = route.name
    end_place_name = route.end_place.name

    response = client.get(url)

    assertContains(response, route_name)
    assertContains(response, end_place_name)


def test_view_route_success_no_end_place(athlete, client):
    route = RouteFactory(end_place=None)
    url = route.get_absolute_url()
    route_name = route.name
    start_place_name = route.start_place.name

    response = client.get(url)

    assertContains(response, route_name)
    assertContains(response, start_place_name)


####################
# view routes:edit #
####################


def test_get_route_edit_form(athlete, client):
    route = RouteFactory(athlete=athlete)
    url = route.get_absolute_url("edit")
    response = client.get(url)
    content = '<h2 class="text-center mrgb0">{}</h2>'.format(route.name)
    assertContains(response, content, html=True)


def test_get_route_edit_form_not_logged(athlete, client):
    route = RouteFactory(athlete=athlete)
    url = route.get_absolute_url("edit")
    client.logout()

    response = client.get(url)
    redirect_url = "/login/?next=" + url

    assertRedirects(response, redirect_url)


def test_post_route_edit_form(athlete, client):
    route = RouteFactory(athlete=athlete)
    url = route.get_absolute_url("edit")
    post_data = {
        "name": route.name,
        "activity_type": 2,
    }

    response = client.post(url, post_data)
    redirect_url = route.get_absolute_url()

    assertRedirects(response, redirect_url)


def test_post_route_remove_checkpoints(
    athlete,
    client,
):
    number_of_checkpoints = 10
    route = create_route_with_checkpoints(number_of_checkpoints, athlete=athlete)
    route_data = model_to_dict(route)
    post_data = {
        key: value for key, value in route_data.items() if key in RouteForm.Meta.fields
    }
    checkpoints_data = [
        "_".join([str(checkpoint.place.id), str(checkpoint.line_location)])
        for checkpoint in route.checkpoint_set.all()
    ]
    post_data["checkpoints"] = checkpoints_data[: number_of_checkpoints - 3]
    url = route.get_absolute_url("edit")
    client.post(url, post_data)

    assert route.checkpoint_set.count(), number_of_checkpoints - 3


def test_get_route_edit_not_owner(athlete, client):
    route = RouteFactory(athlete=AthleteFactory())
    url = route.get_absolute_url("edit")
    response = client.get(url)
    assert response.status_code == 403


def test_post_route_edit_not_owner(athlete, client):
    route = RouteFactory(athlete=AthleteFactory())
    url = route.get_absolute_url("edit")
    post_data = {"name": route.name}
    response = client.post(url, post_data)

    assert response.status_code == 403


######################
# view routes:update #
######################


def test_get_route_update(athlete, client, mock_route_details_response):
    route = RouteFactory(athlete=athlete, data_source="switzerland_mobility")
    url = route.get_absolute_url("update")

    mock_route_details_response(
        data_source=route.data_source,
        source_id=route.source_id,
        api_response_json="2191833_show.json",
    )
    response = client.get(url)

    remote_route_name = "Haute Cime"
    content = '<h2 class="text-center mrgb0">{}</h2>'.format(remote_route_name)
    assertContains(response, content, html=True)


def test_post_route_update(athlete, client, mock_route_details_response):
    route = RouteFactory(athlete=athlete, data_source="switzerland_mobility")
    url = route.get_absolute_url("update")
    post_data = {
        "name": route.name,
        "activity_type": route.activity_type.id,
    }
    mock_route_details_response(
        data_source=route.data_source,
        source_id=route.source_id,
    )
    response = client.post(url, post_data)
    assertRedirects(response, route.get_absolute_url())


def test_get_route_update_not_owner(athlete, client, mock_route_details_response):
    route = RouteFactory(athlete=AthleteFactory(), data_source="switzerland_mobility")
    url = route.get_absolute_url("update")
    post_data = {"name": route.name}
    response = client.post(url, post_data)
    assert response.status_code == 403


def test_post_route_update_not_owner(athlete, client, mock_route_details_response):
    route = RouteFactory(athlete=AthleteFactory(), data_source="switzerland_mobility")
    url = route.get_absolute_url("update")
    post_data = {"name": route.name}
    response = client.post(url, post_data)
    assert response.status_code == 403


def test_get_route_update_404(athlete, client):
    url = resolve_url("routes:update", pk=666)
    response = client.get(url)
    assert response.status_code == 404


######################
# view routes:delete #
######################


def test_get_route_delete_view(athlete, client):
    route = RouteFactory(athlete=athlete)
    url = route.get_absolute_url("delete")

    response = client.get(url)
    content = "<h1>Delete %s</h1>" % route.name
    assertContains(response, content, html=True)


def test_get_route_delete_not_logged(athlete, client):
    route = RouteFactory(athlete=athlete)
    url = route.get_absolute_url("delete")
    client.logout()
    response = client.get(url)

    redirect_url = "/login/?next=" + url
    assertRedirects(response, redirect_url)


def test_post_route_delete_view(athlete, client):
    route = RouteFactory(athlete=athlete)
    url = route.get_absolute_url("delete")
    post_data = {}
    response = client.post(url, post_data)

    redirect_url = reverse("routes:routes")
    assertRedirects(response, redirect_url)


def test_get_route_delete_not_owner(athlete, client):
    route = RouteFactory(athlete=AthleteFactory())
    url = route.get_absolute_url("delete")
    response = client.get(url)

    assert response.status_code == 403


def test_post_route_delete_not_owner(athlete, client):
    route = RouteFactory(athlete=AthleteFactory())
    url = route.get_absolute_url("delete")
    post_data = {}
    response = client.post(url, post_data)

    assert response.status_code == 403


################################
# view routes:checkpoints_list #
################################


def test_get_checkpoints_list_empty(athlete, client):
    route = RouteFactory(athlete=athlete)
    url = reverse("routes:checkpoints_list", args=[route.pk])
    response = client.get(url)
    assert response.status_code == 200
    assert not response.json()["checkpoints"]


def test_get_checkpoints_list(athlete, client, switzerland_mobility_data_from_json):
    number_of_checkpoints = 20
    geom = LineString([(x, 0) for x in range(number_of_checkpoints + 2)])
    route = RouteFactory(athlete=athlete, start_place=None, end_place=None, geom=geom)

    # checkpoints
    create_checkpoints_from_geom(route.geom, number_of_checkpoints)
    url = reverse("routes:checkpoints_list", args=[route.pk])
    response = client.get(url)

    assert response.status_code == 200
    assert len(response.json()["checkpoints"]) == number_of_checkpoints


#######################
# Management Commands #
#######################


@pytest.mark.django_db
def test_cleanup_hdf5_files_no_data():
    out = StringIO()

    call_command("cleanup_hdf5_files", "--dry-run", stdout=out)
    assert "No files to delete." in out.getvalue()

    call_command("cleanup_hdf5_files", stdout=out)
    assert "No files to delete." in out.getvalue()


@pytest.mark.django_db
def test_cleanup_hdf5_files_routes():
    out = StringIO()

    # five routes no extra files
    RouteFactory.create_batch(5)

    call_command("cleanup_hdf5_files", "--dry-run", stdout=out)
    assert "No files to delete." in out.getvalue()

    call_command("cleanup_hdf5_files", stdout=out)
    assert "No files to delete." in out.getvalue()


@pytest.mark.django_db
def test_cleanup_hdf5_files_delete_trash():
    out = StringIO()
    data_dir = Path(settings.MEDIA_ROOT, "data")
    data_dir.mkdir(parents=True, exist_ok=True)

    for i in range(5):
        filename = uuid4().hex + ".h5"
        full_path = data_dir / filename
        with full_path.open(mode="wb") as file_:
            file_.write(urandom(64))

    call_command("cleanup_hdf5_files", "--dry-run", stdout=out)
    message = "Clean-up command would delete 5 and keep 0 files."
    assert message in out.getvalue()

    call_command("cleanup_hdf5_files", stdout=out)
    assert "Successfully deleted 5 files." in out.getvalue()


@pytest.mark.django_db
def test_cleanup_hdf5_files_missing_route_file():
    out = StringIO()

    # 5 routes, include one to use the filepath
    route, *_ = RouteFactory.create_batch(5)
    field = DataFrameField()
    full_path = field.storage.path(route.data.filepath)
    data_dir = Path(full_path).parent.resolve()

    # delete one route file
    file_to_delete = list(data_dir.glob("*"))[0]
    (data_dir / file_to_delete).unlink()

    # add one random file
    filename = uuid4().hex + ".h5"
    full_path = data_dir / filename
    with full_path.open(mode="wb") as file_:
        file_.write(urandom(64))

    call_command("cleanup_hdf5_files", "--dry-run", stdout=out)
    message = "Clean-up command would delete 1 and keep 4 files."
    assert message in out.getvalue()
    assert "1 missing file(s):" in out.getvalue()

    call_command("cleanup_hdf5_files", stdout=out)
    assert "Successfully deleted 1 files." in out.getvalue()
    assert "1 missing file(s):" in out.getvalue()


@pytest.mark.django_db
def test_cleanup_hdf5_files_directory_as_file():
    out = StringIO()

    # 1 route
    route = RouteFactory()
    field = DataFrameField()
    full_path = field.storage.path(route.data.filepath)
    data_dir = Path(full_path).parent.resolve()

    # add one random directory with .h5 extension
    dirname = "dir.h5"
    full_path = data_dir / dirname
    Path(full_path).mkdir(parents=True, exist_ok=True)

    with pytest.raises(CommandError):
        call_command("cleanup_hdf5_files", stdout=out)
