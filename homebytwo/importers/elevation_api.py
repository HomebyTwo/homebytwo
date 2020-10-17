import logging
from typing import Iterator, List, Tuple, Optional

from django.conf import settings
from django.contrib.gis.geos import LineString

import requests

ELEVATION_API_ENDPOINT = "https://elevation-api.io/api/elevation"
MAX_NUMBER_OF_POINTS = 250

logger = logging.getLogger(__name__)


def elevation_lookup(
    coords: List[Tuple[float, float]], session
) -> Optional[List[float]]:
    """
    looks up a list of elevations for a list of coordinates: [(lat,lng),(lat,lng)]
    of maximum 250 points.
    """

    # enforce maximum number of points per request
    message = "Elevation API error: maximum number of points per request exceeded."
    assert len(coords) <= MAX_NUMBER_OF_POINTS, message

    # POST request to the elevation API
    resolution = settings.ELEVATION_API_RESOLUTION
    response = session.post(
        ELEVATION_API_ENDPOINT,
        params={"resolution": resolution},
        json={"points": coords},
    )

    # raise exception in case of error
    response.raise_for_status()

    # parse response json
    response_json = response.json()
    elevations = [point["elevation"] for point in response_json["elevations"]]

    # log error if wrong resolution is returned
    if response_json["resolution"] != resolution:
        message = "Elevation API returned a bad resolution {}"
        logger.error(message.format(response_json["resolution"]))
        return

    # log error if elevation lookup returned a -9999
    if -9999 in elevations:
        message = "Elevation API returned missing value."
        logger.error(message)
        return

    return elevations


def chunk(list_of_items: List, max_number_of_items: int) -> Iterator[List]:
    start, end = 0, max_number_of_items
    while list_of_items[start:end]:
        yield list_of_items[start:end]
        start += max_number_of_items
        end += max_number_of_items


def get_elevations_from_coords(
    coords: List[Tuple[float, float]]
) -> Optional[List[float]]:
    """
    splits up the number of coordinates in chunks of max number of points per request
    and triggers the elevation lookups with a shared requests session.
    """
    session = requests.Session()
    session.headers.update({"ELEVATION-API-KEY": settings.ELEVATION_API_KEY})

    elevations = []
    for coords_subset in chunk(coords, MAX_NUMBER_OF_POINTS):
        elevation_subset = elevation_lookup(coords_subset, session)

        if elevation_subset:
            elevations.extend(elevation_subset)
        else:
            return

    return elevations


def get_elevations_from_geom(geom: LineString) -> Optional[List[float]]:
    # do not even try if the API key is missing
    if not settings.ELEVATION_API_KEY:
        message = "No key set for the Elevation API."
        logger.warning(message)
        return

    # prepare coords in 4326 lat, lng
    linestring = geom.transform(4326, clone=True)
    coords = [(lat, lng) for lng, lat in linestring]

    # retrieve elevations from coords
    elevations = get_elevations_from_coords(coords)

    # ensure API returned elevation points, error was logged during lookup
    if not elevations:
        return

    # ensure number of elevation points returned corresponds to the number of coords
    if not len(elevations) == len(coords):
        message = "Elevation API returned wrong number of elevation points."
        logger.error(message)
        return

    return elevations
