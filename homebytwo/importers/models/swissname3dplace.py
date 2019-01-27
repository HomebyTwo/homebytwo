from django.contrib.gis.db import models

from ...routes.models import Place


class Swissname3dManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(data_source='swissname3d')


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
        'Alpiner Gipfel': Place.SUMMIT,
        'Ausfahrt': Place.EXIT,
        'Aussichtspunkt': Place.POINT_OF_VIEW,
        'Bildstock': Place.WAYSIDE_SHRINE,
        'Brunnen': Place.FOUNTAIN,
        'Denkmal': Place.MONUMENT,
        'Ein- und Ausfahrt': Place.ENTRY_AND_EXIT,
        'Erratischer Block': Place.BOULDER,
        'Felsblock': Place.BELAY,
        'Felskopf': Place.BELAY,
        'Flurname swisstopo': Place.LOCAL_PLACE,
        'Gebaeude Einzelhaus': Place.SINGLE_BUILDING,
        'Gebaeude': Place.SINGLE_BUILDING,
        'Gipfel': Place.SUMMIT,
        'Grotte, Hoehle': Place.CAVE,
        'Haltestelle Bahn': Place.TRAIN_STATION,
        'Haltestelle Bus': Place.BUS_STATION,
        'Haltestelle Schiff': Place.BOAT_STATION,
        'Hauptgipfel': Place.SUMMIT,
        'Haupthuegel': Place.HILL,
        'Huegel': Place.HILL,
        'Kapelle': Place.CHAPEL,
        'Landesgrenzstein': Place.LANDMARK,
        'Lokalname swisstopo': Place.PLACE,
        'Offenes Gebaeude': Place.OPEN_BUILDING,
        'Pass': Place.PASS,
        'Quelle': Place.SOURCE,
        'Sakrales Gebaeude': Place.SACRED_BUILDING,
        'Strassenpass': Place.ROAD_PASS,
        'Turm': Place.TOWER,
        'Uebrige Bahnen': Place.OTHER_STATION,
        'Verladestation': Place.LOADING_STATION,
        'Verzweigung': Place.INTERCHANGE,
        'Wasserfall': Place.WATERFALL,
        'Zollamt 24h 24h': Place.CUSTOMHOUSE_24H,
        'Zollamt 24h eingeschraenkt': Place.CUSTOMHOUSE_24H_LIMITED,
        'Zollamt eingeschraenkt': Place.CUSTOMHOUSE_LIMITED,
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
            super().save(*args, **kwargs)
