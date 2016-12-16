from __future__ import unicode_literals

from routes.models import Place

# translation map for type of places
PLACE_TYPE_TRANSLATIONS = {
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
    'Grotte, Hoehle': 'Grotto: Cave',
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


class Swissname3dPlace(Place):
    """
    Extends Place Model with attributes and methods specific to SwissNAME3D.
    swissNAMES3D is the most comprehensive collection of geographical names
    for Switzerland and Liechtenstein.
    https://opendata.swiss/en/dataset/swissnames3d-geografische-namen-der-landesvermessung1
    """

    def save(self, *args, **kwargs):
        """
        Places from the SwissNAME3D_PKT file are imported
        with the command './manage.py importswissname3d shapefile'.
        If a place is already in the database, it is skipped.
        To refresh the data, call the command with the '--delete' option
        """

        # Skip if the record is already in the Database
        if Swissname3dPlace.objects.filter(source_id=self.source_id).exists():
            pass
        else:
            # Translate place type from German to English.
            self.place_type = PLACE_TYPE_TRANSLATIONS[self.place_type]

            # Save with the parent method
            super(Swissname3dPlace, self).save(*args, **kwargs)
