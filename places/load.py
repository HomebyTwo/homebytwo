import os
from django.contrib.gis.utils import LayerMapping
from .models import Place
from django.contrib import settings

swissplaces_mapping = {
    'place_type' : 'OBJEKTART',
    'altitude' : 'HOEHE',
    'name' : 'NAME',
    'geom' : 'MULTIPOINT25D',
}

swissplaces_shp = os.path.abspath(
    os.path.join(settings.BASE_DIR, 'media', 'shapefiles', 'swissNAMES3D_PKT.shp'),
)

def run(verbose=True):
    lm = LayerMapping(
        Place, swissplaces_shp, swissplaces_mapping,
        transform=False, encoding='UTF-8',
    )
    lm.save(strict=True, verbose=verbose)