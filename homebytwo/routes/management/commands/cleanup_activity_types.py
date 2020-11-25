from django.core.management import BaseCommand
from django.db.models import Q

from homebytwo.routes.models import Activity, ActivityType


class Command(BaseCommand):

    help = "Remove activity types that are unsupported or have no associated activity. "

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            "--dryrun",
            action="store_false",
            dest="delete",
            default=True,
            help="test to command outcome.",
        )

    def handle(self, *args, **options):
        supported_activity_types = ActivityType.SUPPORTED_ACTIVITY_TYPES
        activities = Activity.objects.exclude(
            activity_type__name__in=supported_activity_types
        )

        activity_types = ActivityType.objects.filter(
            Q(activities=None) | ~Q(name__in=supported_activity_types)
        ).distinct()

        activities_count = activities.count()
        activity_types_count = activity_types.count()

        if options["delete"]:
            activities.delete()
            activity_types.delete()
            message = "Deleted "
        else:
            message = "Would delete "

        message += "{} activities and {} activity_types.".format(
            activities_count, activity_types_count
        )
        return message
