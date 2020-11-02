from io import StringIO, TextIOWrapper
from zipfile import ZipFile

from django.core.management import call_command
from django.core.management.base import CommandError

import pytest
from requests import ConnectionError, HTTPError

from ...routes.models import Place
from ...routes.models.place import PlaceTuple, PlaceType
from ...routes.tests.factories import PlaceFactory
from ..geonames import PLACE_DATA_URL as GEO_DATA_URL
from ..geonames import (
    PLACE_TYPE_URL,
    get_geonames_remote_file,
    import_places_from_geonames,
    update_place_types_from_geonames,
)
from ..swissnames3d import PLACE_DATA_URL as SWISS_DATA_URL
from ..swissnames3d import (
    get_swissnames3d_remote_file,
    import_places_from_swissnames3d,
    unzip_swissnames3d_remote_file,
)
from ..utils import download_zip_file, get_csv_line_count, save_places_from_generator

#########
# utils #
#########


def test_get_csv_line_count(open_file):
    csv_file = open_file("swissnames3d_LV03_test.csv")
    assert get_csv_line_count(csv_file, header=True) == 202
    assert get_csv_line_count(csv_file, header=False) == 203
    assert csv_file.tell() == 0


def test_get_csv_line_count_empty_file(open_file):
    csv_file = open_file("text.txt")
    assert get_csv_line_count(csv_file, header=True) == 0
    assert get_csv_line_count(csv_file, header=False) == 0
    assert csv_file.tell() == 0


def test_download_zip_file(mock_zip_response):
    url = GEO_DATA_URL.format(scope="LI")
    mock_zip_response(url, "geonames_LI.zip", content_length="13091")
    assert isinstance(download_zip_file(url), ZipFile)


def test_download_zip_file_not_found(mock_html_not_found):
    url = GEO_DATA_URL.format(scope="ZZ")
    mock_html_not_found(url)
    with pytest.raises(HTTPError, match=f"404 Client Error: Not Found for url: {url}"):
        download_zip_file(url)


@pytest.mark.django_db
def test_save_places_from_generator():
    existing_places = PlaceFactory.create_batch(5, data_source="geonames")
    new_places = PlaceFactory.build_batch(20, data_source="geonames")
    places = existing_places + new_places

    data = (
        PlaceTuple(
            name=place.name,
            place_type=place.place_type.code,
            latitude=place.geom.y,
            longitude=place.geom.x,
            altitude=place.altitude,
            source_id=place.source_id,
            data_source=place.data_source,
            srid=4326,
        )
        for place in places
    )
    msg = "Created 20 new places and updated 5 places. "
    assert save_places_from_generator(data, count=20, update=True) == msg
    assert Place.objects.count() == 25


@pytest.mark.django_db
def test_save_places_from_generator_empty():
    places = []
    data = (place for place in places)
    msg = "Created 0 new places and updated 0 places. "
    assert save_places_from_generator(data, count=0, update=False) == msg
    assert Place.objects.count() == 0


@pytest.mark.django_db
def test_save_places_from_generator_bad_place_type(capsys):

    place = PlaceFactory.build(data_source="geonames")
    place.place_type.code = "BADCODE"
    data = (
        PlaceTuple(
            name=place.name,
            place_type=place.place_type.code,
            latitude=place.geom.y,
            longitude=place.geom.x,
            altitude=place.altitude,
            source_id=place.source_id,
            data_source=place.data_source,
            srid=4326,
        )
        for place in [place]
    )
    msg = "Created 0 new places and updated 0 places. "
    assert save_places_from_generator(data, count=1, update=True) == msg
    captured = capsys.readouterr()
    assert "Place type code: BADCODE does not exist.\n" in captured.out
    assert Place.objects.count() == 0


###############
# geonames.py #
###############


def test_get_geonames_remote_file(mock_zip_response):
    url = GEO_DATA_URL.format(scope="LI")
    mock_zip_response(url, "geonames_LI.zip", content_length="13091")
    assert isinstance(get_geonames_remote_file(scope="LI"), TextIOWrapper)


def test_get_geonames_remote_file_not_found(mock_html_not_found):
    url = GEO_DATA_URL.format(scope="ZZ")
    mock_html_not_found(url)
    with pytest.raises(HTTPError):
        get_geonames_remote_file(scope="ZZ")


def test_get_geonames_remote_file_connection_error(mock_connection_error):
    url = GEO_DATA_URL.format(scope="XX")
    mock_connection_error(url)
    with pytest.raises(ConnectionError):
        get_geonames_remote_file(scope="XX")


@pytest.mark.django_db
def test_import_places_from_geonames_local_file(open_file):
    file = open_file("geonames_LI.txt")
    msg = "Created 200 new places and updated 0 places. "
    assert import_places_from_geonames(file=file) == msg


def test_import_places_from_geonames_not_found(mock_html_not_found):
    scope = "ZZ"
    url = GEO_DATA_URL.format(scope=scope)
    mock_html_not_found(url)
    msg = f"File for {scope} could not be downloaded from geonames.org: "
    assert msg in import_places_from_geonames("ZZ")


@pytest.mark.django_db
def test_update_place_types_from_geonames(mock_html_response):
    url = PLACE_TYPE_URL
    assert PlaceType.objects.count() == 681
    mock_html_response(url, "geonames_codes_one.html")
    mock_html_response(url, "geonames_codes.html")
    update_place_types_from_geonames()
    assert PlaceType.objects.count() == 1
    update_place_types_from_geonames()
    assert PlaceType.objects.count() == 681


##################
# swissnames3d.py #
##################


def test_get_swissnames3d_remote_file(mock_zip_response):
    url = SWISS_DATA_URL
    mock_zip_response(url, "swissnames3d_data.zip", content_length="70171")
    assert isinstance(get_swissnames3d_remote_file(), TextIOWrapper)


def test_unzip_swissnames3d_remote_file(open_file):
    zip_file = ZipFile(open_file("swissnames3d_data.zip", binary=True))
    text_file = unzip_swissnames3d_remote_file(zip_file)
    assert isinstance(text_file, TextIOWrapper)
    assert text_file.name == "swissNAMES3D_LV95/csv_LV95_LN02/swissNAMES3D_PKT.csv"


@pytest.mark.django_db
def test_import_places_from_swissnames3d(open_file):
    file = open_file("swissnames3d_LV03_test.csv")
    msg = "Created 146 new places and updated 0 places. "
    assert import_places_from_swissnames3d(projection="LV03", file=file) == msg


##################################
# import_geonames_places command #
##################################


@pytest.mark.django_db
def test_import_geonames_places(mock_zip_response):
    scope = "LI"
    url = GEO_DATA_URL.format(scope=scope)
    mock_zip_response(url, "geonames_LI.zip", content_length="13091")

    out = StringIO()
    call_command("import_geonames_places", scope, stdout=out)

    msg = "Created 200 new places and updated 0 places. "
    assert msg in out.getvalue()
    assert Place.objects.filter(data_source="geonames").count() == 200


@pytest.mark.django_db
def test_import_geonames_places_multiple(
    mock_zip_response, mock_html_not_found, mock_connection_error, current_dir_path
):
    mock_zip_response(GEO_DATA_URL.format(scope="LI"), "geonames_LI.zip", content_length="13091")
    mock_html_not_found(GEO_DATA_URL.format(scope="ZZ"))
    mock_connection_error(GEO_DATA_URL.format(scope="XX"))
    file_path = current_dir_path / "data/geonames_LI.txt"

    out = StringIO()
    call_command(
        "import_geonames_places",
        "LI",
        "ZZ",
        "XX",
        "--update",
        "-f",
        file_path.as_posix(),
        stdout=out,
    )

    msgs = [
        "Created 200 new places and updated 0 places. ",
        "Created 0 new places and updated 200 places. ",
        "File for ZZ could not be downloaded from geonames.org: ",
        f'Error connecting to {GEO_DATA_URL.format(scope="XX")}. ',
    ]
    assert all([msg in out.getvalue() for msg in msgs])


def test_import_geonames_places_no_param(mock_zip_response):
    with pytest.raises(CommandError):
        call_command("import_geonames_places")


######################################
# import_geonames_places command #
######################################


@pytest.mark.django_db
def test_import_swissnames3d_places(mock_zip_response):
    url = SWISS_DATA_URL
    mock_zip_response(url, "swissnames3d_data.zip", content_length="70171")

    out = StringIO()
    call_command("import_swissnames3d_places", stdout=out)

    msg = "Created 146 new places and updated 0 places. "
    assert msg in out.getvalue()
    assert Place.objects.filter(data_source="swissnames3d").count() == 146


@pytest.mark.django_db
def test_import_swissnames3d_places_projection(mock_zip_response):
    url = SWISS_DATA_URL
    mock_zip_response(url, "swissnames3d_data.zip", content_length="70171")

    out = StringIO()
    call_command("import_swissnames3d_places", "-p", "LV03", stdout=out)

    msg = "Created 146 new places and updated 0 places. "
    assert msg in out.getvalue()
    assert Place.objects.filter(data_source="swissnames3d").count() == 146


@pytest.mark.django_db
def test_import_swissnames3d_places_file(current_dir_path):
    file_path = current_dir_path / "data/swissnames3d_LV95_test.csv"
    out = StringIO()
    call_command("import_swissnames3d_places", "-u", "-f", file_path.as_posix(), stdout=out)

    msg = "Created 146 new places and updated 46 places. "
    assert msg in out.getvalue()
    assert Place.objects.filter(data_source="swissnames3d").count() == 146


def test_import_swissnames3d_places_connection_error(mock_connection_error):
    mock_connection_error(SWISS_DATA_URL)
    out = StringIO()
    call_command("import_swissnames3d_places", stdout=out)

    msg = f"Error connecting to {SWISS_DATA_URL}. "
    assert msg in out.getvalue()


def test_import_swissnames3d_places_not_found(mock_html_not_found):
    mock_html_not_found(SWISS_DATA_URL)
    out = StringIO()
    call_command("import_swissnames3d_places", stdout=out)

    msg = f"Error downloading {SWISS_DATA_URL}: "
    assert msg in out.getvalue()
