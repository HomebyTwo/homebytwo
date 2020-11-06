import argparse

from django.core.management import BaseCommand, CommandError

from ...geonames import import_places_from_geonames


class Command(BaseCommand):

    help = "Import places from geonames.org"

    def add_arguments(self, parser):
        # path to an optional local file instead of downloading from the remote service
        parser.add_argument(
            "-f",
            "--files",
            type=argparse.FileType("r"),
            nargs="*",
            default=None,
            help="Provide local files instead of downloading. ",
        )

        # choose import scope
        parser.add_argument(
            "countries",
            type=str,
            nargs="*",
            default=None,
            help="Choose countries to import from, e.g. FR. ",
        )

    def handle(self, *args, **options):

        files = options["files"] or []
        for file in files:
            msg = import_places_from_geonames(file=file)
            self.stdout.write(self.style.SUCCESS(msg))

        countries = options["countries"] or []
        for country in countries:
            msg = import_places_from_geonames(scope=country)
            self.stdout.write(self.style.SUCCESS(msg))

        if not files and not countries:
            raise CommandError("Please provide a country or a file. ")
