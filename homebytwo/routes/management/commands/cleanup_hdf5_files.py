import os
from glob import glob

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from ...fields import DataFrameField


class Command(BaseCommand):
    help = "Clean up unused HDF5 files from the media folder"

    def handle(self, *args, **options):
        dataframe_fields = self.list_dataframe_fields()
        db_file_set = self.list_db_files(dataframe_fields)
        os_file_set = self.list_os_files()
        files_to_delete = os_file_set - db_file_set

        if files_to_delete:
            number_files_deleted = self.delete_files(files_to_delete)
            message = "Successfully deleted {} files.".format(number_files_deleted)
            self.stdout.write(self.style.SUCCESS(message))
        else:
            self.stdout.write("No files to delete.")

    def list_dataframe_fields(self):
        """
        return all model fields of type DataFrameField as tupple (model, field)
        """

        dataframe_fields = []

        for model in apps.get_models():
            dataframe_fields.extend(
                [
                    (model, field)
                    for field in model._meta.get_fields()
                    if isinstance(field, DataFrameField)
                ]
            )

        return dataframe_fields

    def list_db_files(self, dataframe_fields):
        """
        return a set of all files saved by dataframe fields in the database
        """
        db_file_list = []

        for model, field in dataframe_fields:
            if field.column:
                query = "SELECT {column} FROM {db_table}".format(
                    column=field.column, db_table=model._meta.db_table,
                )

                with connection.cursor() as cursor:
                    cursor.execute(query)
                    db_files = [column[0] for column in cursor.fetchall()]
                    cursor.close()

                db_file_list.extend([field.get_absolute_path(file) for file in db_files])

        # remove duplicates
        return set(db_file_list)

    def list_os_files(self):
        """
        list all .h5 files in media folders
        """
        media_folder = settings.MEDIA_ROOT
        os_file_list = glob(media_folder + '/**/*.h5', recursive=True)
        return set(os_file_list)

    def delete_files(self, files_to_delete):
        """
        remove obsolete files from the filesystem
        """
        for file in files_to_delete:
            try:
                os.remove(file)
            except OSError as error:
                raise CommandError("{} could not be deleted: {}".format(file, error))

        return len(files_to_delete)
