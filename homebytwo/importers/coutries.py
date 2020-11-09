import json

from django.contrib.gis.geos import GEOSGeometry

import requests

from homebytwo.routes.models.country import Country

GEO_COUNTRIES_URL = (
    "https://raw.githubusercontent.com/"
    "datasets/geo-countries/master/data/countries.geojson"
)


def import_country_geometries():
    print("importing country geometries...")
    response = requests.get(GEO_COUNTRIES_URL)
    response.raise_for_status()
    geom_json = response.json()
    for country in geom_json["features"]:
        defaults = {
            "name": country["properties"]["ADMIN"],
            "iso2": country["properties"]["ISO_A2"],
            "geom": GEOSGeometry(json.dumps(country["geometry"])),
        }
        Country.objects.update_or_create(
            iso3=country["properties"]["ISO_A3"],
            defaults=defaults,
        )
