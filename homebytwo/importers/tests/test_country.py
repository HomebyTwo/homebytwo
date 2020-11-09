import pytest
from requests.exceptions import ConnectionError

from ...routes.models import Country
from ..coutries import GEO_COUNTRIES_URL, import_country_geometries

#########
# model #
#########


@pytest.mark.django_db
def test_country_str():
    country = Country.objects.last()
    assert str(country) == country.name


################
# countries.py #
################


@pytest.mark.django_db
def test_import_country_geometries(mock_json_response):
    Country.objects.all().delete()
    url = GEO_COUNTRIES_URL
    file = "countries.geojson"
    mock_json_response(url, file)

    import_country_geometries()

    assert Country.objects.count() == 4
    countries = ["Yemen", "Switzerland", "Germany", "South Africa"]
    for country in countries:
        assert country in Country.objects.values_list("name", flat=True)


@pytest.mark.django_db
def test_import_country_geometries_connection_error(mock_connection_error):
    url = GEO_COUNTRIES_URL
    mock_connection_error(url)
    with pytest.raises(ConnectionError):
        import_country_geometries()
