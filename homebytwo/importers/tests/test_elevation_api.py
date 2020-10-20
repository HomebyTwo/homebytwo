import logging

from django.contrib.gis.geos import LineString

import pytest
from requests import Session

from homebytwo.importers.elevation_api import (MAX_NUMBER_OF_POINTS, chunk,
                                               elevation_lookup,
                                               get_elevations_from_coords,
                                               get_elevations_from_geom)
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
    assert not get_elevations_from_geom(route.geom)
    message = "No key set for the Elevation API."
    assert message in caplog.text


def test_get_elevation_from_geom_bad_response(
    settings, add_elevation_responses, caplog
):
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
def test_update_route_elevation_data_task_fail(
    settings, add_elevation_responses, caplog
):
    settings.ELEVATION_API_KEY = "api-key"
    route = RouteFactory()
    add_elevation_responses(MAX_NUMBER_OF_POINTS, resolution="5000m")
    response = update_route_elevation_data_task(route.pk)

    assert "Elevation API returned a bad resolution" in caplog.text
    content = f"Error while retrieving elevation data for route with id: {route.id}."
    assert response == content
