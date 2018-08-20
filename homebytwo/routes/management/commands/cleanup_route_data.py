import os

from django.db import connection
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Clean up unused HDF files used to store route data'

    def handle(self, *args, **options):

        # list all files in the file system

        # directory where files are saved, `data` is configured in the Track model
        data_dir = os.path.join(
            settings.BASE_DIR,
            settings.MEDIA_ROOT,
            'data',
        )

        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        # list all files and filter by .h5 extension
        os_files = os.listdir(data_dir)
        hdf_os_files = {file for file in os_files if file[-3:] == '.h5'}

        # list all files in the Database
        cursor = connection.cursor()
        cursor.execute('SELECT data FROM routes_route')
        db_files = {column[0] for column in cursor.fetchall()}

        # delete os files that are not in the DB
        files_to_delete = hdf_os_files - db_files

        if files_to_delete:
            for file in files_to_delete:
                try:
                    os.remove(os.path.join(data_dir, file))
                except OSError:
                    raise CommandError('{} could not be deleted'.format(file))

            # Announce success
            file_count = len(files_to_delete)
            message = 'Successfully deleted {} files.'.format(file_count)
            self.stdout.write(self.style.SUCCESS(message))

        else:
            self.stdout.write('No files to delete.')
