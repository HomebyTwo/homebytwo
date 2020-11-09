import csv
from io import TextIOWrapper
from typing import IO, Iterator, Optional

import requests
from lxml import html
from requests import ConnectionError, HTTPError

from ..routes.models.place import PlaceTuple, PlaceType
from .utils import download_zip_file, get_csv_line_count, save_places_from_generator

PLACE_TYPE_URL = "http://www.geonames.org/export/codes.html"
PLACE_DATA_URL = "https://download.geonames.org/export/dump/{scope}.zip"


def import_places_from_geonames(
    scope: str = "allCountries",
    file: Optional[TextIOWrapper] = None,
) -> str:
    """
    import places from https://www.geonames.org/

    :param scope: two letter country abbreviation (ISO-3166 alpha2;
    see https://www.geonames.org/countries/), e.g. `CH` or `allCountries`
    :param file: path to local unzipped file. If provided, the `scope` parameter
    will be ignored and the local file will be used.
    """
    try:
        file = file or get_geonames_remote_file(scope)
    except HTTPError as error:
        return f"File for {scope} could not be downloaded from geonames.org: {error}. "
    except ConnectionError:
        return f"Error connecting to {PLACE_DATA_URL.format(scope=scope)}. "

    with file:
        count = get_csv_line_count(file, header=False)
        data = parse_places_from_csv(file)
        source_info = f"geonames.org {scope}"

        return save_places_from_generator(data, count, source_info)


def get_geonames_remote_file(scope: str = "allCountries") -> TextIOWrapper:
    """
    retrieve zip file from https://download.geonames.org/export/dump/

    :param scope: ISO-3166 alpha2 country abbreviation, e.g. `FR` or `allCountries`
    """
    zip_file = download_zip_file(PLACE_DATA_URL.format(scope=scope))

    return TextIOWrapper(zip_file.open(f"{scope}.txt"))


def parse_places_from_csv(file: IO) -> Iterator[PlaceTuple]:
    """
    generator function to parse a geonames.org CSV file

    geonames.org CSV files are delimited by a tab character (\t) have no header row
    and the following columns:
    0: geonameid          : integer id of record in geonames database
    1: name               : name of geographical point (utf8) varchar(200)
    2: asciiname          : name of geographical point in plain ascii characters,
       varchar(200)
    3: alternatenames     : alternatenames, comma separated, ascii names automatically
                            transliterated, convenience attribute from alternatename
                            table, varchar(10000)
    4: latitude           : latitude in decimal degrees (wgs84)
    5: longitude          : longitude in decimal degrees (wgs84)
    6: feature class      : see http://www.geonames.org/export/codes.html, char(1)
    7: feature code       : see http://www.geonames.org/export/codes.html, varchar(10)
    8: country code       : ISO-3166 2-letter country code, 2 characters
    9: cc2                : alternate country codes, comma separated, ISO-3166 2-letter
                            country code, 200 characters
    10: admin1 code       : fipscode (subject to change to iso code), see exceptions
                            below, see file admin1Codes.txt for display names of this
                            code; varchar(20)
    11: admin2 code       : code for the second administrative division, a county in
                            the US, see file admin2Codes.txt; varchar(80)
    12: admin3 code       : code for third level administrative division, varchar(20)
    13: admin4 code       : code for fourth level administrative division, varchar(20)
    14: population        : bigint (8 byte int)
    15: elevation         : in meters, integer
    16: dem               : digital elevation model, srtm3 or gtopo30, average elevation
                            of 3''x3'' (ca 90mx90m) or 30''x30'' (ca 900mx900m) area in
                            meters, integer. srtm processed by cgiar/ciat.
    17: timezone          : the iana timezone id (see file timeZone.txt) varchar(40)
    18: modification date : date of last modification in yyyy-MM-dd format
    """
    data_reader = csv.reader(file, delimiter="\t")
    for row in data_reader:
        if row[0] and row[1] and row[4] and row[5] and row[7]:
            yield PlaceTuple(
                data_source="geonames",
                source_id=int(row[0]),
                name=row[1],
                country=row[8],
                latitude=float(row[4]),
                longitude=float(row[5]),
                place_type=row[7],
                altitude=float(row[14]),
                srid=4326,
            )


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
            defaults = {
                "feature_class": current_feature_class,
                "name": name,
                "description": description,
            }
            PlaceType.objects.update_or_create(
                code=code,
                defaults=defaults,
            )
