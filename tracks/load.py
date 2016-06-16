import os
from django.contrib.gis.utils import LayerMapping
from .models import SwissPlaces

swissplaces_mapping = {
    'uuid' : 'UUID',
    'place_type' : 'OBJEKTART',
    'altitude' : 'HOEHE',
    'name_uuid' : 'NAME_UUID',
    'name' : 'NAME',
    'lang_code' : 'SPRACHCODE',
    'name_type' : 'NAMEN_TYP',
    'name_group' : 'NAMENGRUPP',
    'geom' : 'MULTIPOINT25D',
}

swissplaces_shp = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'data', 'shp', 'swissNAMES3D_PKT.shp'),
)

def run(verbose=True):
    lm = LayerMapping(
        SwissPlaces, swissplaces_shp, swissplaces_mapping,
        transform=False, encoding='UTF-8',
    )
    lm.save(strict=True, verbose=verbose)