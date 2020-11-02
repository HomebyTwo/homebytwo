import csv
from io import TextIOWrapper
from typing import Iterator, Optional
from zipfile import ZipFile

from requests import ConnectionError, HTTPError

from ..routes.models.place import PlaceTuple
from .utils import download_zip_file, get_csv_line_count, save_places_from_generator

PLACE_DATA_URL = "http://data.geo.admin.ch/ch.swisstopo.swissnames3d/data.zip"
PROJECTION_SRID = {"LV03": 21781, "LV95": 2056}

# translation map for type of places
PLACE_TYPE_TRANSLATIONS = {
    "Alpiner Gipfel": "PK",
    "Ausfahrt": "RDJCT",
    "Aussichtspunkt": "PROM",
    "Bildstock": "SHRN",
    "Brunnen": "WTRW",
    "Denkmal": "MNMT",
    "Ein- und Ausfahrt": "RDJCT",
    "Erratischer Block": "RK",
    "Felsblock": "RK",
    "Felskopf": "CLF",
    "Flurname swisstopo": "PPLL",
    "Gebaeude Einzelhaus": "BLDG",
    "Gebaeude": "BLDG",
    "Gipfel": "PK",
    "Grotte, Hoehle": "CAVE",
    "Haltestelle Bahn": "RSTP",
    "Haltestelle Bus": "BUSTP",
    "Haltestelle Schiff": "LDNG",
    "Hauptgipfel": "PK",
    "Haupthuegel": "HLL",
    "Huegel": "HLL",
    "Kapelle": "CH",
    "Landesgrenzstein": "BP",
    "Lokalname swisstopo": "PPL",
    "Offenes Gebaeude": "BLDG",
    "Pass": "PASS",
    "Quelle": "SPNG",
    "Sakrales Gebaeude": "CH",
    "Strassenpass": "PASS",
    "Turm": "TOWR",
    "Uebrige Bahnen": "RSTP",
    "Verladestation": "TRANT",
    "Verzweigung": "RDJCT",
    "Wasserfall": "FLLS",
    "Zollamt 24h 24h": "PSTB",
    "Zollamt 24h eingeschraenkt": "PSTB",
    "Zollamt eingeschraenkt": "PSTB",
}


def import_places_from_swissnames3d(
    projection: str = "LV95", file: Optional[TextIOWrapper] = None, update: bool = False
) -> str:
    """
    import places from SwissNAMES3D

    :param projection: "LV03" or "LV95"
    see http://mapref.org/CoordinateReferenceFrameChangeLV03.LV95.html#Zweig1098
    :param file: path to local unzipped file. if provided, the `projection`
    parameter will be ignored.
    :param update: should existing places be updated with the downloaded data.
    """
    try:
        file = file or get_swissnames3d_remote_file(projection=projection)
    except HTTPError as error:
        return f"Error downloading {PLACE_DATA_URL}: {error}. "
    except ConnectionError:
        return f"Error connecting to {PLACE_DATA_URL}. "

    count = get_csv_line_count(file, header=True)
    data = parse_places_from_csv(file, projection=projection)

    return save_places_from_generator(data=data, count=count, update=update)


def get_swissnames3d_remote_file(projection: str = "LV95") -> TextIOWrapper:
    """
    :param projection: "LV03" or "LV95"
    """
    zip_root = download_zip_file(PLACE_DATA_URL)
    return unzip_swissnames3d_remote_file(zip_root, projection)


def unzip_swissnames3d_remote_file(
    zip_file: ZipFile, projection: str = "LV95"
) -> TextIOWrapper:
    """
    unzip the csv file corresponding to the requested projection
    """
    # a zip inside a zip
    zip_name = f"swissNAMES3D_{projection}.zip"
    print(f"unzipping {zip_name}")
    inner_zip = ZipFile(zip_file.open(zip_name))

    # e.g. swissNAMES3D_LV03/csv_LV03_LN02/swissNAMES3D_PKT.csv
    file_name = f"swissNAMES3D_{projection}/csv_{projection}_LN02/swissNAMES3D_PKT.csv"
    print(f"extracting {file_name}")
    return TextIOWrapper(inner_zip.open(file_name))


def parse_places_from_csv(
    file: TextIOWrapper, projection: str = "LV95"
) -> Iterator[PlaceTuple]:
    """
    generator function to parse a CSV file from swissnames3d

    swissnames3d CSV files are delimited by a semi-colon character (;) have a header row
    and the following columns:
    0:  UUID             : feature UUID
    1:  OBJEKTART        : feature type, see
    2:  OBJEKTKLASSE_TLM : feature class
    3:  HOEHE            : elevation
    4:  GEBAEUDENUTZUNG  : building use
    5:  NAME_UUID        : name UUID
    6:  NAME             : name
    7:  STATUS           : name status: official, foreign or usual
    8:  SPRACHCODE       : language
    9:  NAMEN_TYP        : type of name: simple name, endonym or name pair: Biel/Bienne
    10: NAMENGRUPPE_UUID : name group UUID
    11: E                : longitude in the projection's coordinate system
    12: N                : latitude in the projection's coordinate system
    13: Z                : elevation
    """
    # initialize csv reader
    data_reader = csv.reader(file, delimiter=";")

    # skip header row
    next(data_reader)

    for row in data_reader:
        if row[7] == "offiziell":
            yield PlaceTuple(
                data_source="swissnames3d",
                source_id=row[0],
                name=row[6],
                longitude=float(row[11]),
                latitude=float(row[12]),
                place_type=PLACE_TYPE_TRANSLATIONS[row[1]],
                altitude=float(row[13]),
                srid=PROJECTION_SRID[projection],
            )
