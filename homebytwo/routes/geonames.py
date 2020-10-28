import csv
from collections import namedtuple
from io import BytesIO, TextIOWrapper
from typing import IO, Iterator
from zipfile import ZipFile

from django.db import transaction
from django.contrib.gis.geos import Point

from lxml import html
import requests
from tqdm import tqdm

from homebytwo.routes.models import Place, Route
from homebytwo.routes.models.place import PlaceType

PLACE_TYPE_URL = "http://www.geonames.org/export/codes.html"
PLACE_DATA_URL = "https://download.geonames.org/export/dump/{}.zip"

PlaceTuple = namedtuple(
    "PlaceTuple", ["geonameid", "name", "latitude", "longitude", "feature_code", "elevation"]
)


def import_places_from_geonames(scope: str = "allCountries"):
    file = get_geonames_remote_file(scope)
    data = parse_places_from_file(file)
    create_places_from_geonames_data(data)


def get_geonames_remote_file(scope: str = "allCountries") -> IO[bytes]:
    """
    retrieve zip file from https://download.geonames.org/export/dump/
    """
    print(f"downloading geonames file for `{scope}`...")
    response = requests.get(f"https://download.geonames.org/export/dump/{scope}.zip")
    response.raise_for_status()
    root = ZipFile(BytesIO(response.content))
    return TextIOWrapper(root.open(f"{scope}.txt"))


def get_geonames_local_file(file_name: str) -> IO:
    """
    open a local file to pass to the generator.
    """
    return TextIOWrapper(open(file_name))


def count_rows_in_file(file: IO) -> int:
    return sum(1 for _ in csv.reader(file))


def parse_places_from_file(file: IO) -> Iterator[PlaceTuple]:
    data_reader = csv.reader(file, delimiter="\t")
    for row in data_reader:
        if row[0] and row[1] and row[4] and row[5] and row[7]:
            yield PlaceTuple(
                geonameid=int(row[0]),
                name=row[1],
                latitude=float(row[4]),
                longitude=float(row[5]),
                feature_code=row[7],
                elevation=float(row[14]),
            )


def create_places_from_geonames_data(data: Iterator[PlaceTuple], count: int) -> None:
    description = "saving geonames places"
    with transaction.atomic():
        for remote_place in tqdm(data, desc=description, total=count):
            default_values = {
                "name": remote_place.name,
                "place_type": PlaceType.objects.get(code=remote_place.feature_code),
                "geom": Point(remote_place.longitude, remote_place.latitude, srid=4326),
                "altitude": remote_place.elevation,
            }

            local_place, created = Place.objects.get_or_create(
                data_source="geonames",
                source_id=remote_place.geonameid,
                defaults=default_values,
            )

            if not created:
                for key, value in default_values.items():
                    setattr(local_place, key, value)
                local_place.save()


def update_place_types_from_geonames() -> None:
    """
    Scrape the page containing the reference of all features type
    at http://www.geonames.org/export/codes.html and save the
    result to the database.
    """
    # retrieve page content with requests
    print("importing place types from geonames... ")
    response = requests.get(PLACE_TYPE_URL)
    response.raise_for_status()

    # target table
    xml = html.fromstring(response.content)
    feature_type_table = xml.xpath('//table[@class="restable"]')[0]

    # parse place types from table rows
    table_rows = feature_type_table.xpath(".//tr")
    place_type_pks = []
    for row in table_rows:

        # header rows contain class information
        if row.xpath(".//th"):
            header_text = row.text_content()
            feature_class, class_description = header_text.split(" ", 1)
            current_feature_class = feature_class

        # non-header rows contain feature type
        elif "tfooter" not in row.classes:
            code, name, description = [
                element.text_content() for element in row.xpath(".//td")
            ]
            place_type, created = PlaceType.objects.get_or_create(
                feature_class=current_feature_class,
                code=code,
                name=name,
                description=description,
            )
            place_type_pks.append(place_type.pk)

    PlaceType.objects.exclude(pk__in=place_type_pks).delete()


def migrate_route_checkpoints_to_geonames() -> None:
    print("migrating route checkpoints...")
    total_count = Route.objects.all().count()
    for index, route in enumerate(Route.objects.all(), 1):
        print(f"{index}/{total_count} migrating route: {route}")
        existing_checkpoints = route.checkpoint_set
        existing_checkpoint_names = existing_checkpoints.values_list(
            "place__name", flat=True
        )
        possible_checkpoints = route.find_possible_checkpoints()
        for checkpoint in possible_checkpoints:
            if (
                checkpoint.place.name in existing_checkpoint_names
                and checkpoint.place.data_source == "geonames"
            ):
                checkpoint.save()
