from django.contrib.gis.geos import Point
from django.core.management import BaseCommand

from pandas import DataFrame
from stravalib.exc import AccessUnauthorized, ObjectNotFound

from homebytwo.importers.exceptions import (SwitzerlandMobilityError,
                                            SwitzerlandMobilityMissingCredentials)
from homebytwo.routes.models import Route
from homebytwo.routes.utils import get_distances


def interpolate_from_existing_data(route: Route) -> bool:
    """
    use existing route data to restore distance and altitude data
    """
    new_data = DataFrame({"distance": get_distances([Point(p) for p in route.geom])})
    new_data["line_location"] = new_data.distance / new_data.distance.max()
    new_data["altitude"] = route.get_data(new_data.line_location, "altitude")
    route.data = new_data
    return True


class Command(BaseCommand):
    help = "fix routes with mismatching coordinates and altitude"

    def handle(self, *args, **options):
        verbosity = options["verbosity"]

        # counter for display
        import_count = restore_count = 0

        if verbosity:
            message = "Fixing routes with mismatching coordinates and altitude data..."
            self.stdout.write(message)

        for route in Route.objects.all():

            # discard routes with matching geom and data
            if len(route.geom) == len(route.data.distance):
                continue

            # try to get data from source
            try:
                route.geom, route.data = route.get_route_data()
                if verbosity > 1:
                    print(f"Re-imported route: {route} from {route.data_source}.")
                import_count += 1
            except (
                SwitzerlandMobilityError,
                SwitzerlandMobilityMissingCredentials,
                AccessUnauthorized,
                ObjectNotFound,
            ):
                # fallback on existing route data
                interpolate_from_existing_data(route)
                if verbosity > 1:
                    print(f"Restored route: {route} from {route.data_source} with existing data.")
                restore_count += 1

            route.update_permanent_track_data(commit=False)
            route.update_track_details_from_data(commit=False)
            route.save()

        if verbosity:
            message = "Re-imported {} routes and restored {} from data.".format(
                import_count, restore_count
            )
            self.stdout.write(self.style.SUCCESS(message))
