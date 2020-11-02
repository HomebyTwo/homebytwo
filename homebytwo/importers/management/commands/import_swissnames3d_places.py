import argparse

from django.core.management.base import BaseCommand

from ...swissnames3d import import_places_from_swissnames3d


class Command(BaseCommand):

    help = "Import places from SwissNAMES3D"

    def add_arguments(self, parser):
        # path to an optional local file instead of downloading from the remote service
        parser.add_argument(
            "-f",
            "--file",
            type=argparse.FileType("r"),
            nargs="?",
            default=None,
            help="Provide a local file path instead of downloading. ",
        )

        # choose Swiss projection
        parser.add_argument(
            "-p",
            "--projection",
            type=str,
            nargs="?",
            default="LV95",
            help="Choose a swiss projection LV95 (default) or LV03. ",
        )

        # update existing places
        parser.add_argument(
            "-u",
            "--update",
            action="store_true",
            default=False,
            help="Update existing places with remote data. ",
        )

    def handle(self, *args, **options):
        file = options["file"]
        projection = options["projection"]
        update = options["update"]
        msg = import_places_from_swissnames3d(projection, file, update)
        self.stdout.write(self.style.SUCCESS(msg))
