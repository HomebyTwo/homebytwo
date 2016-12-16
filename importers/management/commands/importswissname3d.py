from django.core.management.base import BaseCommand, CommandError

import os
from ...models import Swissname3dPlace
from django.contrib.gis.utils import LayerMapping
from django.contrib.gis.gdal import DataSource

# Make input work in Python 2.7
if hasattr(__builtins__, 'raw_input'):
    input = raw_input


class Command(BaseCommand):

    help = 'Import from the SwissNAME3D points shapefile to the Place Model'

    def query_yes_no(self, question, default="yes"):
        """Ask a yes/no question via raw_input() and return their answer.
        http://stackoverflow.com/questions/3041986/apt-command-line-interface-like-yes-no-input

        "question" is a string that is presented to the user.
        "default" is the presumed answer if the user just hits <Enter>.
            It must be "yes" (the default), "no" or None (meaning
            an answer is required of the user).

        The "answer" return value is True for "yes" or False for "no".
        """
        valid = {"yes": True, "y": True, "ye": True,
                 "no": False, "n": False}
        if default is None:
            prompt = " [y/n] "
        elif default == "yes":
            prompt = " [Y/n] "
        elif default == "no":
            prompt = " [y/N] "
        else:
            raise ValueError("invalid default answer: '%s'" % default)

        while True:
            self.stdout.write(question + prompt)
            choice = input().lower()
            if default is not None and choice == '':
                return valid[default]
            elif choice in valid:
                return valid[choice]
            else:
                self.stdout.write("Please respond with 'yes' or 'no' "
                                  "(or 'y' or 'n').\n")

    def add_arguments(self, parser):

        # path to the shapefile
        parser.add_argument(
            'shapefile', type=str,
            help='Path to the shapefile to import. '
        )

        # Limit to number of places
        parser.add_argument(
            '--limit', type=int,
            nargs='?', default=-1,
            help=(
                  'Limits the number of imported features. '
            ),
        )

        # Deletes all existing SwissNAME3D places
        parser.add_argument(
            '--delete', '--drop',
            action='store_true', dest='delete', default=False,
            help=(
                'Deletes all existing SwissNAME3D places before the import. '
            ),
        )

        # runs without asking any questions
        parser.add_argument(
            '--noinput', '--no-input',
            action='store_false', dest='interactive', default=True,
            help=(
                'Tells Django to NOT prompt the user for input of any kind. '
            ),
        )

    def handle(self, *args, **options):

        # Generate path and make sure the file exists
        shapefile = os.path.abspath(options['shapefile'])
        if not os.path.exists(shapefile):
            error_msg = ('The file "%s" could not be found.' % shapefile)
            raise OSError(error_msg)

        # Define mapping between layer fields of the shapefile
        # and fields of Place Model
        swissname3d_mapping = {
            'place_type': 'OBJEKTART',
            'altitude': 'HOEHE',
            'name': 'NAME',
            'geom': 'POINT25D',
            'source_id': 'UUID',
        }

        # Try to map the data
        try:
            layermapping = LayerMapping(
                Swissname3dPlace, shapefile, swissname3d_mapping,
                transform=False, encoding='UTF-8',
            )

        except:
            error_msg = (
                'The shapefile could not be interpreted.\nAre you sure '
                '"%s" is the SwissNAME3D_PKT shapefile?' % shapefile
            )
            raise CommandError(error_msg)

        # Get the number of features
        datasource = DataSource(shapefile)
        layer = datasource[0]
        feature_count = len(layer)

        # Display number of features to import
        limit = options['limit']
        if limit > -1:
            feature_count = min(feature_count, limit)

        # Save the mapped data to the Database
        if options['interactive']:
            self.stdout.write(
                'Saving %d places from %s' % (feature_count, shapefile)
            )

            if not self.query_yes_no('Do you want to continue?'):
                error_msg = (
                    'You have canceled the operation.'
                )
                raise CommandError(error_msg)

        layermapping.save(strict=True, fid_range=(0, feature_count),
                          stream=self.stdout, progress=True)

        # Inform on success
        msg = 'Successfully imported %d places.' % feature_count
        self.stdout.write(self.style.SUCCESS(msg))
