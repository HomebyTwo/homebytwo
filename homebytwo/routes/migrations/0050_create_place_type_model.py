# Generated by Django 2.2.16 on 2020-10-24 12:28
from django.contrib.gis.geos import Point
from django.db import migrations, models

from tqdm import tqdm

from homebytwo.routes.geonames import (
    migrate_route_checkpoints_to_geonames,
    get_geonames_remote_file,
    parse_places_from_file,
    update_place_types_from_geonames,
)


def migrate_routes_to_geonames(apps, schema_editor):
    migrate_route_checkpoints_to_geonames()


def import_place_types_from_geonames(apps, schema_editor):
    update_place_types_from_geonames()


def import_places_from_geonames(apps, schema_editor):
    Place = apps.get_model("routes", "Place")
    PlaceType = apps.get_model("routes", "PlaceType")

    file = get_geonames_remote_file("CH")
    data = parse_places_from_file(file)

    print("saving geonames places")
    for remote_place in data:
        defaults = {
            "name": remote_place.name,
            "place_type": PlaceType.objects.get(code=remote_place.feature_code),
            "geom": Point(remote_place.longitude, remote_place.latitude, srid=4326),
            "altitude": remote_place.elevation,
            "old_place_type": "CST",
        }

        local_place, created = Place.objects.get_or_create(
            data_source="geonames",
            source_id=remote_place.geonameid,
            defaults=defaults,
        )

        if not created:
            local_place.update(defaults)
            local_place.save()


def update_routes(apps, schema_editor):
    migrate_route_checkpoints_to_geonames()


class Migration(migrations.Migration):

    dependencies = [
        ("routes", "0049_merge_20201002_1037"),
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
            import_places_from_geonames,
        ),
        migrations.RunPython(migrate_routes_to_geonames),
    ]
