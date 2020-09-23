from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from ...fields import DataFrameField


class Command(BaseCommand):
    help = "Clean up unused HDF5 files from the media folder"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            "--dryrun",
            action="store_false",
            dest="delete",
            default=True,
            help=("list files that would be deleted, without actually deleting them. "),
        )

    def handle(self, *args, **options):
        dataframe_fields = self.list_dataframe_fields()
        db_file_set = self.list_db_files(dataframe_fields)
        os_file_set = self.list_os_files()
        files_to_delete = os_file_set - db_file_set
        files_to_keep = os_file_set & db_file_set
        missing_files = db_file_set - os_file_set

        if files_to_delete:
            if options["delete"]:
                number_files_deleted = self.delete_files(files_to_delete)
                message = "Successfully deleted {} files.".format(number_files_deleted)
            else:
                for file in files_to_delete:
                    self.stdout.write(f"{file}")
                message = f"Clean-up command would delete {len(files_to_delete)} and keep {len(files_to_keep)} files."
            self.stdout.write(self.style.SUCCESS(message))
        else:
            self.stdout.write("No files to delete.")

        if missing_files:
            self.stdout.write(f"{len(missing_files)} missing file(s):")
            for file in missing_files:
                self.stdout.write(f"{file}")

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
                    column=field.column,
                    db_table=model._meta.db_table,
                )

                with connection.cursor() as cursor:
                    cursor.execute(query)
                    db_files = [column[0] for column in cursor.fetchall()]

                db_file_list.extend(
                    [field.get_absolute_path(file) for file in db_files if file]
                )

        return set(db_file_list)

    def list_os_files(self):
        """
        list all .h5 files in the media folders.
        """
        media_folder = Path(settings.MEDIA_ROOT)
        return {path.resolve().as_posix() for path in media_folder.glob("**/*.h5")}

    def delete_files(self, files_to_delete):
        """
        remove obsolete files from the filesystem
        """
        for file in files_to_delete:
            try:
                Path(file).unlink()
            except OSError as error:
                raise CommandError("{} could not be deleted: {}".format(file, error))

        return len(files_to_delete)
