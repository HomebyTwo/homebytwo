import json
import logging

import pytest
from django.contrib.gis.geos import LineString
from django.forms import model_to_dict
from django.shortcuts import resolve_url
from requests import Session
from pytest_django.asserts import assertRedirects

from homebytwo.importers.elevation_api import (
    chunk,
    elevation_lookup,
    get_elevations_from_coords,
    get_elevations_from_geom,
    MAX_NUMBER_OF_POINTS,
)
from homebytwo.importers.tests.factories import StravaRouteFactory
from homebytwo.routes.forms import RouteForm
from homebytwo.routes.models import Route
from homebytwo.routes.tasks import update_route_elevation_data_task
from homebytwo.routes.tests.factories import RouteFactory


def test_chunk_no_items():
    item_list = list()
    lists = chunk(item_list, 10)
    with pytest.raises(StopIteration):
        next(lists)


def test_chunk_smaller_than_max_number():
    item_list = list(range(10))
    lists = chunk(item_list, 15)

    assert next(lists) == list(range(10))
    with pytest.raises(StopIteration):
        next(lists)


def test_chunk_equal_to_max_number():
    item_list = list(range(10))
    lists = chunk(item_list, 10)

    assert next(lists) == list(range(10))
    with pytest.raises(StopIteration):
        next(lists)


def test_chunk_bigger_than_max_number():
    item_list = list(range(15))
    lists = chunk(item_list, 10)

    assert next(lists) == list(range(10))
    assert next(lists) == list(range(10, 15))
    with pytest.raises(StopIteration):
        next(lists)


def test_elevation_lookup_no_value():
    assert not elevation_lookup([], Session())


def test_elevation_lookup_success(add_elevation_responses):
    geom = LineString((0, 0), (1, 1), (2, 2))
    route = RouteFactory.build(geom=geom)
    add_elevation_responses(len(route.geom))
    coords = [(lat, lng) for lng, lat in route.geom]
    elevations = elevation_lookup(coords, Session())

    assert len(elevations) == len(route.geom)
    assert elevations == list(range(3))


def test_elevation_lookup_too_many_points():
    route = RouteFactory.build()
    coords = [(lat, lng) for lng, lat in route.geom]
    with pytest.raises(AssertionError):
        elevation_lookup(coords, Session())


def test_elevation_lookup_wrong_resolution(add_elevation_responses, caplog):
    geom = LineString((0, 0), (1, 1), (2, 2))
    route = RouteFactory.build(geom=geom)
    coords = [(lat, lng) for lng, lat in route.geom]
    add_elevation_responses(len(route.geom), resolution="5000m")
    assert not elevation_lookup(coords, Session())
    assert "Elevation API returned a bad resolution" in caplog.text


def test_elevation_lookup_missing_value(add_elevation_responses, caplog):
    geom = LineString((0, 0), (1, 1), (2, 2))
    route = RouteFactory.build(geom=geom)
    add_elevation_responses(len(route.geom), missing_value=True)
    coords = [(lat, lng) for lng, lat in route.geom]
    assert not elevation_lookup(coords, Session())
    assert "Elevation API returned missing value." in caplog.text


def test_get_elevation_from_coords_empty():
    assert not get_elevations_from_coords([])


def test_get_elevations_from_coords_success(add_elevation_responses):
    route = RouteFactory.build()
    coords = [(lat, lng) for lng, lat in route.geom]
    add_elevation_responses(len(coords))
    elevations = get_elevations_from_coords(coords)
    assert len(elevations) == len(route.geom)


def test_get_elevations_from_coords_bad_response(add_elevation_responses):
    route = RouteFactory.build()
    coords = [(lat, lng) for lng, lat in route.geom]
    add_elevation_responses(1, resolution="5000m")
    assert not get_elevations_from_coords(coords)


def test_get_elevations_from_geom(settings, add_elevation_responses):
    settings.ELEVATION_API_KEY = "api-key"
    route = RouteFactory.build()
    add_elevation_responses(len(route.geom))
    elevations = get_elevations_from_geom(route.geom)
    assert len(elevations) == len(route.geom)


def test_get_elevations_from_geom_no_key(settings, caplog):
    settings.ELEVATION_API_KEY = ""
    route = RouteFactory.build()
    elevations = get_elevations_from_geom(route.geom)
    assert not get_elevations_from_geom(route.geom)
    message = "No key set for the Elevation API."
    assert message in caplog.text


def test_get_elevation_from_geom_bad_response(settings, add_elevation_responses, caplog):
    settings.ELEVATION_API_KEY = "api-key"
    route = RouteFactory.build()
    add_elevation_responses(len(route.geom) - 1)
    assert not get_elevations_from_geom(route.geom)
    message = "Elevation API returned wrong number of elevation points."
    assert message in caplog.text


@pytest.mark.django_db
def test_update_route_elevation_data_task(settings, add_elevation_responses, caplog):
    settings.ELEVATION_API_KEY = "api-key"
    caplog.set_level(logging.INFO)
    route = RouteFactory()
    add_elevation_responses(len(route.geom))
    response = update_route_elevation_data_task(route.pk)

    assert f"retrieving elevation data for route with id: {route.id}." in caplog.text
    assert f"Elevation updated for route: {route}." in response
    route.refresh_from_db()
    assert route.data.altitude.tolist() == list(range(len(route.geom)))


@pytest.mark.django_db
def test_update_route_elevation_data_task_fail(settings, add_elevation_responses, caplog):
    settings.ELEVATION_API_KEY = "api-key"
    route = RouteFactory()
    add_elevation_responses(MAX_NUMBER_OF_POINTS, resolution="5000m")
    response = update_route_elevation_data_task(route.pk)

    assert "Elevation API returned a bad resolution" in caplog.text
    content = f"Error while retrieving elevation data for route with id: {route.id}."
    assert response == content


def test_import_strava_route(
    athlete,
    caplog,
    celery,
    client,
    import_route_response,
    mocker,
    read_file,
    settings,
):
    settings.STRAVA_ROUTE_URL = "https://example.com/routes/%d"
    route = StravaRouteFactory.build(
        athlete=athlete,
        start_place=None,
        end_place=None,
    )

    post_data = dict(
        filter(
            lambda item: item[0] in RouteForm.Meta.fields and item[1],
            model_to_dict(route).items(),
        )
    )
    post_data["activity_type"] = 1
    response = import_route_response(
        route.data_source,
        route.source_id,
        method="post",
        post_data=post_data,
    )

    new_route = Route.objects.get(
        athlete=athlete,
        data_source=route.data_source,
        source_id=route.source_id,
    )

    mock_elevation_task = mocker.patch(
        "homebytwo.routes.tasks.update_route_elevation_data_task.run"
    )
    assert mock_elevation_task.called_with(route.id)
    assertRedirects(response, resolve_url(new_route))
