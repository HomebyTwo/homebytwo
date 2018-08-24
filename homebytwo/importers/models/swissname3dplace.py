from django.contrib.gis.db import models

from ...routes.models import Place


class Swissname3dManager(models.Manager):
    def get_queryset(self):
        return super(Swissname3dManager, self).get_queryset().filter(
            data_source='swissname3d')


class Swissname3dPlace(Place):
    """
    Extends the Place Model with methods specific to SwissNAME3D.
    Model inheritance is achieved with a proxy model,
    to preserve performance when importing >200'000 places from the shapefile.
    SwissNAMES3D is the most comprehensive collection of geographical names
    for Switzerland and Liechtenstein.
    https://opendata.swiss/en/dataset/swissnames3d-geografische-namen-der-landesvermessung
    """

    # translation map for type of places
    PLACE_TYPE_TRANSLATIONS = {
        'Flurname swisstopo': 'PLA',
        'Lokalname swisstopo': 'PLA',
        'Haltestelle Bus': 'BUS',
        'Gebaeude': 'BDG',
        'Gebaeude Einzelhaus': 'BDG',
        'Haltestelle Bahn': 'TRA',
        'Hauptgipfel': 'SUM',
        'Pass': 'PAS',
        'Gipfel': 'SUM',
        'Huegel': 'HIL',
        'Haupthuegel': 'HIL',
        'Felskopf': 'BEL',
        'Uebrige Bahnen': 'OTH',
        'Ausfahrt': 'EXT',
        'Haltestelle Schiff': 'BOA',
        'Alpiner Gipfel': 'SUM',
        'Kapelle': 'CPL',
        'Offenes Gebaeude': 'OBG',
        'Strassenpass': 'RPS',
        'Verzweigung': 'ICG',
        'Sakrales Gebaeude': 'SBG',
        'Wasserfall': 'WTF',
        'Turm': 'TWR',
        'Zollamt 24h 24h': 'C24',
        'Grotte, Hoehle': 'CAV',
        'Quelle': 'SRC',
        'Ein- und Ausfahrt': 'EAE',
        'Denkmal': 'MNT',
        'Bildstock': 'SHR',
        'Felsblock': 'BLD',
        'Erratischer Block': 'BLD',
        'Zollamt 24h eingeschraenkt': 'C24LT',
        'Brunnen': 'FTN',
        'Zollamt eingeschraenkt': 'CLT',
        'Verladestation': 'LST',
        'Aussichtspunkt': 'POV',
        'Landesgrenzstein': 'LMK',
    }

    objects = Swissname3dManager()

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        """
        PLAs from the SwissNAME3D_PKT file are imported
        with the command './manage.py importswissname3d shapefile'.
        If a place is already in the database, it is skipped.
        To refresh the data, call the command with the '--delete' option
        """

        # Skip if the record is already in the Database
        if Swissname3dPlace.objects.filter(source_id=self.source_id).exists():
            pass
        else:
            # Translate place type from German to English.
            self.place_type = self.PLACE_TYPE_TRANSLATIONS[self.place_type]
            # set datasource to swissname3d
            self.data_source = 'swissname3d'
            # Save with the parent method
            super(Swissname3dPlace, self).save(*args, **kwargs)
