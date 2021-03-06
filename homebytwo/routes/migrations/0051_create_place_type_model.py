# Generated by Django 2.2.16 on 2020-10-24 12:28
from collections import namedtuple

from django.db import migrations, models

from tqdm import tqdm

from homebytwo.importers.geonames import update_place_types_from_geonames

PlaceTypeTuple = namedtuple("PlaceType", ["code", "place_class", "name", "description"])


def import_place_types_from_geonames(apps, schema_editor):
    update_place_types_from_geonames()


def import_place_types_for_swissnames3d(apps, schema_editor):
    PlaceType = apps.get_model("routes", "PlaceType")

    swissnames3d_types = [
        PlaceTypeTuple(
            code="SBDG",
            place_class="S",
            name="sacred building",
            description=(
                " sacred building of a particular religion or denomination "
                "(church, mosque, synagogue, temple, etc.)"
            ),
        ),
        PlaceTypeTuple(
            code="BOSTP",
            place_class="R",
            name="boat stop",
            description=(
                " a place where boats stop to pick up and unload passengers and freight"
            ),
        ),
        PlaceTypeTuple(
            code="OSTP",
            place_class="R",
            name="other public transport stop",
            description=(
                " a place where other public transport "
                "stop to pick up and unload passengers and freight"
            ),
        ),
    ]

    for place_type in swissnames3d_types:
        defaults = {
            "name": place_type.name,
            "feature_class": place_type.place_class,
            "description": place_type.description,
        }
        PlaceType.objects.update_or_create(code=place_type.code, defaults=defaults)


def migrate_place_types(apps, schema_editor):
    place_type_translations = {
        "BDG": "SBDG",
        "BEL": "CLF",
        "BLD": "RK",
        "BOA": "BOSTP",
        "BUS": "BUSTP",
        "C24": "PSTB",
        "C24LT": "PSTB",
        "CAV": "CAVE",
        "CLT": "PSTB",
        "CPL": "CH",
        "EAE": "RDJCT",
        "EXT": "RDJCT",
        "FTN": "WTRW",
        "HIL": "HLL",
        "ICG": "RDJCT",
        "LMK": "BP",
        "LPL": "PPLL",
        "LST": "TRANT",
        "MNT": "MNMT",
        "OBG": "BLDG",
        "OTH": "OSTP",
        "PAS": "PASS",
        "PLA": "PPL",
        "POV": "PROM",
        "RPS": "PASS",
        "SBG": "CH",
        "SHR": "SHRN",
        "SRC": "SPNG",
        "SUM": "PK",
        "TRA": "RSTP",
        "TWR": "TOWR",
        "WTF": "FLLS",
    }
    Place = apps.get_model("routes", "Place")
    PlaceType = apps.get_model("routes", "PlaceType")

    for old, new in tqdm(
        place_type_translations.items(),
        desc="updating places to new place types",
        unit="types",
        unit_scale=True,
        total=len(place_type_translations),
    ):
        try:
            new_place_type = PlaceType.objects.get(code=new)
        except PlaceType.DoesNotExist:
            print(f"Place type {new} does not exist")
            Place.objects.filter(old_place_type=old).delete()

        Place.objects.filter(old_place_type=old).update(place_type=new_place_type)


def migrate_swissnames3d_data_source(apps, schema_editor):
    print("updating data_source of swissnames3d places")
    Place = apps.get_model("routes", "Place")
    Place.objects.filter(data_source="swissname3d").update(data_source="swissnames3d")


class Migration(migrations.Migration):

    dependencies = [
        ("routes", "0050_fix_route_data"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlaceType",
            fields=[
                (
                    "feature_class",
                    models.CharField(
                        choices=[
                            ("A", "country, state, region,..."),
                            ("H", "stream, lake,..."),
                            ("L", "parks,area,..."),
                            ("P", "city, village,..."),
                            ("R", "road, railroad"),
                            ("S", "spot, building, farm"),
                            ("U", "undersea"),
                            ("V", "forest,heath,..."),
                        ],
                        max_length=1,
                    ),
                ),
                (
                    "code",
                    models.CharField(max_length=10, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=256)),
                ("description", models.CharField(max_length=512)),
            ],
        ),
        migrations.RunPython(
            import_place_types_from_geonames,
        ),
        migrations.RunPython(
            import_place_types_for_swissnames3d,
        ),
        migrations.RenameField(
            model_name="place",
            old_name="place_type",
            new_name="old_place_type",
        ),
        migrations.AddField(
            model_name="place",
            name="place_type",
            field=models.ForeignKey(
                on_delete="CASCADE", to="routes.PlaceType", null=True
            ),
        ),
        migrations.RunPython(
            migrate_place_types,
        ),
        migrations.RunPython(
            migrate_swissnames3d_data_source,
        ),
        migrations.RemoveField(
            model_name="place",
            name="old_place_type",
        ),
        migrations.AlterField(
            model_name="place",
            name="place_type",
            field=models.ForeignKey(on_delete="CASCADE", to="routes.PlaceType"),
        ),
        migrations.RemoveField(
            model_name="place",
            name="public_transport",
        ),
        migrations.AlterField(
            model_name="place",
            name="source_id",
            field=models.CharField(
                max_length=50, null=True, verbose_name="ID at the data source"
            ),
        ),
    ]
