import csv
from io import TextIOWrapper
from tempfile import TemporaryFile
from typing import Iterator
from zipfile import ZipFile

from django.contrib.gis.geos import Point
from django.db import transaction
from django.http import Http404

from requests import Session, codes
from requests.exceptions import ConnectionError
from tqdm import tqdm

from ..routes.models import Country, Place, PlaceType, Route
from ..routes.models.place import PlaceTuple
from .exceptions import SwitzerlandMobilityError, SwitzerlandMobilityMissingCredentials


def request_json(url, cookies=None):
    """
    Makes a get call to an url to retrieve a json from Switzerland Mobility
    while trying to handle server and connection errors.
    """
    with Session() as session:
        try:
            response = session.get(url, cookies=cookies)

        # connection error and inform the user
        except ConnectionError:
            message = "Connection Error: could not connect to {url}. "
            raise ConnectionError(message.format(url=url))

        else:
            # if request is successful return json object
            if response.status_code == codes.ok:
                json = response.json()
                return json

            # client error: access denied
            if response.status_code == 403:
                message = "We could not import this route. "

                # athlete is logged-in to Switzerland Mobility
                if cookies:
                    message += (
                        "Ask the route creator to share it"
                        "publicly on Switzerland Mobility. "
                    )
                    raise SwitzerlandMobilityError(message)

                # athlete is not logged-in to Switzerland Mobility
                else:
                    message += (
                        "If you are the route creator, try logging-in to"
                        "Switzerland mobility. If the route is not yours,"
                        "ask the creator to share it publicly. "
                    )
                    raise SwitzerlandMobilityMissingCredentials(message)

            # server error: display the status code
            else:
                message = "Error {code}: could not retrieve information from {url}"
                raise SwitzerlandMobilityError(
                    message.format(code=response.status_code, url=url)
                )


def split_routes(remote_routes, local_routes):
    """
    splits the list of remote routes in  3 groups: new, existing and deleted
    """

    # routes in remote service but not in homebytwo
    new_routes = [
        remote_route
        for remote_route in remote_routes
        if remote_route.source_id
        not in [local_route.source_id for local_route in local_routes]
    ]

    # routes in both remote service and homebytwo
    existing_routes = [
        local_route
        for local_route in local_routes
        if local_route.source_id
        in [remote_route.source_id for remote_route in remote_routes]
    ]

    # routes in homebytwo but deleted in remote service
    deleted_routes = [
        local_route
        for local_route in local_routes
        if local_route.source_id
        not in [remote_route.source_id for remote_route in remote_routes]
    ]

    return new_routes, existing_routes, deleted_routes


def get_proxy_class_from_data_source(data_source):
    """
    retrieve route proxy class from "data source" value in the url or raise 404
    """
    route_class = Route(data_source=data_source).proxy_class

    if route_class is None:
        raise Http404("Data Source does not exist")
    else:
        return route_class


def download_zip_file(url: str) -> ZipFile:
    """
    download zip file from remote url to bytes buffer
    and wrap it in ZipFile
    """

    block_size = 1024
    tmp_file = TemporaryFile()

    with Session() as session:
        response = session.get(url, stream=True)
        response.raise_for_status()
        file_size = int(response.headers["Content-Length"])

        for data in tqdm(
            response.iter_content(block_size),
            total=int(file_size / block_size),
            unit="B",
            unit_scale=block_size,
            desc=f"downloading from {url}",
        ):
            tmp_file.write(data)

        return ZipFile(tmp_file)


def get_csv_line_count(csv_file: TextIOWrapper, header: bool) -> int:
    """
    Get the number of features in the csv file
    """
    count = sum(1 for _ in csv.reader(csv_file))
    csv_file.seek(0)  # return the pointer to the first line for reuse

    return max(count - int(header), 0)


def save_places_from_generator(
    data: Iterator[PlaceTuple], count: int, source_info: str
) -> str:
    """
    Save places from csv parsers in geonames.py or swissnames3d.py
    """
    created_counter = updated_counter = 0

    with transaction.atomic():
        for remote_place in tqdm(
            data,
            total=count,
            unit="places",
            unit_scale=True,
            desc=f"saving places from {source_info}",
        ):

            # retrieve PlaceType from the database
            try:
                place_type = PlaceType.objects.get(code=remote_place.place_type)
            except PlaceType.DoesNotExist:
                print(f"Place type code: {remote_place.place_type} does not exist.")
                continue

            # country can be str or Country instance
            country = remote_place.country
            if country and not isinstance(country, Country):
                try:
                    country = Country.objects.get(iso2=remote_place.country)
                except Country.DoesNotExist:
                    print(f"Country code: {remote_place.country} could not be found.")
                    continue

            default_values = {
                "name": remote_place.name,
                "place_type": place_type,
                "country": country,
                "geom": Point(
                    remote_place.longitude,
                    remote_place.latitude,
                    srid=remote_place.srid,
                ),
                "altitude": remote_place.altitude,
            }

            # create or update Place
            _, created = Place.objects.update_or_create(
                data_source=remote_place.data_source,
                source_id=remote_place.source_id,
                defaults=default_values,
            )

            created_counter += int(created)
            updated_counter += int(not created)

        return "Created {} new places and updated {} places. ".format(
            created_counter, updated_counter
        )
