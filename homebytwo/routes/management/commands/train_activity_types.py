from django.core.management import BaseCommand

from homebytwo.routes.models import ActivityType


class Command(BaseCommand):

    help = "Train prediction models for activity types. "

    def add_arguments(self, parser):
        # choose activities
        parser.add_argument(
            "activities",
            type=str,
            nargs="*",
            default=None,
            help="Choose activity types to train. ",
        )

        # Limit to number of places
        parser.add_argument(
            "--limit",
            type=int,
            nargs="?",
            default=None,
            help="Limits the number of activities used for training. ",
        )

    def handle(self, *args, **options):
        if options["activities"]:
            activity_types = ActivityType.objects.filter(name__in=options["activities"])
        else:
            activity_types = ActivityType.objects.all()
        for activity_type in activity_types:
            print(activity_type.train_prediction_model(options["limit"]))

        return f"{activity_types.count()} activity_types trained successfully."
