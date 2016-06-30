import os
from django.contrib.gis.utils import LayerMapping
from .models import Place
from django.contrib import settings
from routes.models import Place
swissplaces_mapping = {
    'type' : 'OBJEKTART',
    'altitude' : 'HOEHE',
    'name' : 'NAME',
    'geom' : 'POINT25D',
    'lang' : 'SPRACHCODE',
}

swissplaces_shp = os.path.abspath(
    os.path.join(
        settings.BASE_DIR,
        'media',
        'shapefiles',
        'swissNAMES3D_PKT.shp',
    ),
)

lang_translations = {
    'Hochdeutsch inkl. Lokalsprachen':'de',
    'Franzoesisch inkl. Lokalsprachen':'fr',
    'Italienisch inkl. Lokalsprachen':'it',
    'Rumantsch Grischun inkl. Lokalsprachen':'rm',
    'Mehrsprachig':'multi',
}

type_translations = {
    'Flurname swisstopo': 'Place',
    'Lokalname swisstopo': 'Place',
    'Haltestelle Bus': 'Bus Station',
    'Gebaeude Einzelhaus': 'Single Building',
    'Haltestelle Bahn': 'Train Station',
    'Hauptgipfel': 'Main Summit',
    'Pass': 'Pass',
    'Gipfel': 'Summit',
    'Huegel': 'Hill',
    'Haupthuegel': 'Main Hill',
    'Felskopf': 'Belay',
    'Uebrige Bahnen': 'Other Station',
    'Ausfahrt': 'Exit',
    'Haltestelle Schiff': 'Boat Station',
    'Alpiner Gipfel': 'Alpine Summit',
    'Kapelle': 'Chapel',
    'Offenes Gebaeude': 'Open Building',
    'Strassenpass': 'Road Pass',
    'Verzweigung': 'Interchange',
    'Sakrales Gebaeude': 'Sacred Building',
    'Wasserfall': 'Waterfall',
    'Turm': 'Tower',
    'Zollamt 24h 24h': 'Customhouse 24h 24h',
    'Grotte: Hoehle': 'Grotto: Cave',
    'Quelle': 'Source',
    'Ein- und Ausfahrt': 'Entry and Exit',
    'Denkmal': 'Monument',
    'Bildstock': 'Wayside shrine',
    'Felsblock': 'Boulder',
    'Erratischer Block': 'Erratic Boulder',
    'Zollamt 24h eingeschraenkt': 'Customhouse 24h limited',
    'Brunnen': 'Fountain',
    'Zollamt eingeschraenkt': 'Customhouse limited',
    'Verladestation': 'Loading Station',
    'Aussichtspunkt': 'Point of View',
    'Landesgrenzstein': 'Landmark',
}
def translate(column, dictionary, model='Place'):
    '''Update inserted German values from Swissnames3d with English translations'''
    for key, value in dictionary.iteritems():
        Place.objects.filter(**{column: key}).update(**{column: value})

def run(verbose=True):
    lm = LayerMapping(
        Place, swissplaces_shp, swissplaces_mapping,
        transform=False, encoding='UTF-8',
    )

    lm.save(strict=True, verbose=verbose)

    translate('lang', lang_translations)
    translate('type', type_translations)

