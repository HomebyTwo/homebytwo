import os

from django.contrib.gis.gdal import DataSource, error as gdal_error

from django.contrib.gis.utils import LayerMapping
from django.core.management.base import BaseCommand, CommandError

from ...models import Swissname3dPlace


class Command(BaseCommand):

    help = 'Import places from the SwissNAME3D_PKT shapefile'

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

    def delete(self, interactive):
        """
        Delete all existing objects from the Database
        """

        places = Swissname3dPlace.objects.all()
        place_count = places.count()

        if interactive:
            self.stdout.write(
                'Deleting %d places from the Database' % (place_count)
            )

            if not self.query_yes_no('Do you want to continue?', 'no'):
                error_msg = (
                    'You have canceled the operation.'
                )
                raise CommandError(error_msg)

        # Delete all places
        places.delete()

        # Inform on successful deletion
        msg = 'Successfully deleted %d places.' % place_count
        self.stdout.write(self.style.SUCCESS(msg))

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
                transform=False, encoding='latin-1',
            )

        except gdal_error.GDALException:
            error_msg = (
                'The shapefile fields could not be interpreted.\nAre you sure '
                '"%s" is the SwissNAME3D_PKT shapefile?' % shapefile
            )
            raise CommandError(error_msg)

        # Delete existing records if requested
        if options['delete']:
            self.delete(options['interactive'])

        mapping_options = {
            'strict': True,
            'stream': self.stdout,
            'progress': True,
        }

        # Get the number of features
        datasource = DataSource(shapefile)
        layer = datasource[0]
        feature_count = len(layer)

        # Display number of features to import
        limit = options['limit']
        if limit > -1:
            feature_count = min(feature_count, limit)
            mapping_options['fid_range'] = (0, limit)
            mapping_options['progress'] = False
        else:
            mapping_options['step'] = 1000

        # Ask for user confirmation
        if options['interactive']:
            self.stdout.write(
                'Saving %d places from %s' % (feature_count, shapefile)
            )

            if not self.query_yes_no('Do you want to continue?'):
                error_msg = (
                    'You have canceled the operation.'
                )
                raise CommandError(error_msg)

        # Save the mapped data to the Database
        self.stdout.write('Importing places...')
        layermapping.save(**mapping_options)

        # Inform on successful save
        msg = 'Successfully imported %d places.' % feature_count
        self.stdout.write(self.style.SUCCESS(msg))
