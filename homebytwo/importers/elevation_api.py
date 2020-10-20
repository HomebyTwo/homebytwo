from typing import Iterator, List, Tuple, Optional

from django.conf import settings
from django.contrib.gis.geos import LineString

import requests
from requests import Session

from homebytwo.importers.exceptions import ElevationAPIError

ELEVATION_API_ENDPOINT = "https://elevation-api.io/api/elevation"
GOOGLE_ELEVATION_API_ENDPOINT = "https://maps.googleapis.com/maps/api/elevation/json"
MAX_NUMBER_OF_POINTS = {"google_elevation_api": 10, "elevation_api": 250}


def google_elevation_api_lookup(
    coords: List[Tuple[float, float]], requests_session: Session
) -> List[float]:
    """
    look up elevations on Google Elevation API
    """

    # GET elevations from to the elevation API
    locations_param = "|".join([f"{lat},{lng}" for lat, lng in coords])
    response = requests_session.get(
        GOOGLE_ELEVATION_API_ENDPOINT,
        params={"key": settings.GOOGLE_API_KEY, "locations": locations_param},
    )

    # raise exception in case of error
    response.raise_for_status()

    # parse response json
    response_json = response.json()

    import ipdb; ipdb.set_trace()

    # raise exception if 200 response is an error:
    if not response_json["status"] == "OK":
        message = "Google Elevation API error. {}: {}".format(
            response_json["status"], response_json["error_message"]
        )
        raise ElevationAPIError(message)

    elevations = [point["elevation"] for point in response_json["results"]]

    return elevations


def elevation_api_lookup(
    coords: List[Tuple[float, float]], requests_session: Session
) -> Optional[List[float]]:
    """
    looks up a list of elevations for a list of coordinates: [(lat,lng),(lat,lng)]
    """

    # POST request to the elevation API
    resolution = settings.ELEVATION_API_RESOLUTION
    response = requests_session.post(
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
        raise ElevationAPIError(message)

    # log error if elevation lookup returned a -9999
    if -9999 in elevations:
        message = "Elevation API returned missing value."
        raise ElevationAPIError(message)

    return elevations


def get_elevations_from_coords(
    coords: List[Tuple[float, float]], provider: str
) -> Optional[List[float]]:
    """
    splits up the number of coordinates in chunks of max number of points per request
    and triggers the elevation lookups with a shared requests session.
    """
    session = requests.Session()
    if provider == "elevation_api":
        session.headers.update(
            {
                "ELEVATION-API-KEY": settings.ELEVATION_API_KEY,
                "Referer": "https://www.homebytwo.ch",
            }
        )

    provider_lookup = {
        "elevation_api": elevation_api_lookup,
        "google_elevation_api": google_elevation_api_lookup,
    }

    elevations = []

    for coords_subset in chunk(coords, MAX_NUMBER_OF_POINTS[provider]):
        elevation_subset = provider_lookup[provider](coords_subset, session)

        if elevation_subset:
            elevations.extend(elevation_subset)
        else:
            return

    return elevations


def get_elevations_from_geom(geom: LineString, provider: str) -> Optional[List[float]]:
    if not has_provider_api_key(provider):
        message = f"No key set for the Elevation API provider: {provider}."
        raise ElevationAPIError(message)

    # prepare coords in 4326 lat, lng
    linestring = geom.transform(4326, clone=True)
    coords = [(lat, lng) for lng, lat in linestring]

    # retrieve elevations from coords
    elevations = get_elevations_from_coords(coords, provider)

    if not elevations:
        message = "Elevation API returned no elevation points, with no errors."
        raise ElevationAPIError(message)

    # ensure number of elevation points returned corresponds to the number of coords
    if not len(elevations) == len(coords):
        message = "Elevation API returned wrong number of elevation points."
        raise ElevationAPIError(message)

    return elevations


def has_provider_api_key(provider: str) -> bool:
    if provider == "elevation_api" and settings.ELEVATION_API_KEY:
        return True
    if provider == "google_elevation_api" and settings.GOOGLE_API_KEY:
        return True
    return False


def chunk(list_of_items: List, max_number_of_items: int) -> Iterator[List]:
    start, end = 0, max_number_of_items
    while list_of_items[start:end]:
        yield list_of_items[start:end]
        start += max_number_of_items
        end += max_number_of_items
