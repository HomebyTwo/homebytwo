import os
from django.contrib.gis.utils import LayerMapping
from .models import Place

swissplaces_mapping = {
    'place_type' : 'OBJEKTART',
    'altitude' : 'HOEHE',
    'name' : 'NAME',
    'geom' : 'MULTIPOINT25D',
}

swissplaces_shp = os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'data', 'shp', 'swissNAMES3D_PKT.shp'),
)

def run(verbose=True):
    lm = LayerMapping(
        Place, swissplaces_shp, swissplaces_mapping,
        transform=False, encoding='UTF-8',
    )
    lm.save(strict=True, verbose=verbose)