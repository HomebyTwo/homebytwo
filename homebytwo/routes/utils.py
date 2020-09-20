from collections import namedtuple
from itertools import accumulate, chain, islice, tee
from pathlib import Path

from django.contrib.gis.db.models.functions import Distance, LineLocatePoint
from django.contrib.gis.measure import D

from .fields import LineSubstring
from .models import ActivityType, Place

# named tupple to handle Urls
Link = namedtuple("Link", ["url", "text"])

GARMIN_ACTIVITY_TYPE_MAP = {
    ActivityType.ALPINESKI: "resort_skiing_snowboarding",
    ActivityType.BACKCOUNTRYSKI: "backcountry_skiing_snowboarding",
    ActivityType.ELLIPTICAL: "elliptical",
    ActivityType.HANDCYCLE: "cycling",
    ActivityType.HIKE: "hiking",
    ActivityType.ICESKATE: "skating",
    ActivityType.INLINESKATE: "skating",
    ActivityType.NORDICSKI: "cross_country_skiing",
    ActivityType.RIDE: "cycling",
    ActivityType.ROCKCLIMBING: "rock_climbing",
    ActivityType.ROWING: "rowing",
    ActivityType.RUN: "running",
    ActivityType.SNOWBOARD: "resort_skiing_snowboarding",
    ActivityType.SNOWSHOE: "hiking",
    ActivityType.STAIRSTEPPER: "fitness_equipment",
    ActivityType.STANDUPPADDLING: "stand_up_paddleboarding",
    ActivityType.SWIM: "swimming",
    ActivityType.VIRTUALRIDE: "cycling",
    ActivityType.VIRTUALRUN: "running",
    ActivityType.WALK: "walk",
    ActivityType.WEIGHTTRAINING: "fitness_equipment",
    ActivityType.WORKOUT: "strength_training",
}


def get_image_path(instance, filename):
    """
    callable to define the image upload path according
    to the type of object: segment, route, etc.. as well as
    the id of the object.
    """
    return Path("images", instance.__class__.__name__, str(instance.id), filename)


def current_and_next(some_iterable):
    """
    use itertools to make current and next item of an iterable available:
    http://stackoverflow.com/questions/1011938/python-previous-and-next-values-inside-a-loop
    used to 'create_segments_from_checkpoints'.
    """
    items, nexts = tee(some_iterable, 2)
    nexts = chain(islice(nexts, 1, None), [None])
    return zip(items, nexts)


def create_segments_from_checkpoints(checkpoints, start=0, end=1):
    """
    returns a list of segments as tuples with start and end locations
    along the original line.
    """

    # sorted list of line_locations from the list of places as
    # well as the start and the end location of the segment where
    # the places were found.
    line_locations = chain(
        [start], [checkpoint.line_location for checkpoint in checkpoints], [end]
    )

    # use the custom iterator, exclude segments where start and end
    # locations are the same. Also exclude segment where 'nxt == None`.
    segments = [
        (crt, nxt)
        for crt, nxt in current_and_next(line_locations)
        if crt != nxt and nxt
    ]

    return segments


def get_places_from_segment(segment, line, max_distance):
    """
    find places within the segment of a line and annotate them with
    the line location on the original line.
    """
    start, end = segment

    # create the Linestring geometry
    subline = LineSubstring(line, start, end)

    # find places within max_distance of the linestring
    places = get_places_from_line(subline, max_distance)

    # iterate over found places to change the line_location
    # from the location on the segment to the location on
    # the original linestring.
    for place in places:
        # relative line location to the start point of the subline
        length = place.line_location * (end - start)

        # update attribute with line location on the original line
        place.line_location = start + length

    return places


def get_places_from_line(line, max_distance):
    """
    returns places within a max_distance of a Linestring Geometry
    ordered by, and annotated with the `line_location` and the
    `distance_from_line`:
        * `line_location` is the location on the line expressed as a
        float between 0.0 and 1.0.
        * `distance_from_line` is a geodjango Distance object.
    """

    # convert max_distance to Distance object
    max_d = D(m=max_distance)

    # find all places within max distance from line
    places = Place.objects.filter(geom__dwithin=(line, max_d))

    # annotate with distance to line
    places = places.annotate(distance_from_line=Distance("geom", line))

    # annotate with location along the line between 0 and 1
    places = places.annotate(line_location=LineLocatePoint(line, "geom"))

    # remove start and end places within 1% of start and end location
    places = places.filter(line_location__gt=0.01, line_location__lt=0.99,)

    # sort in order of apparence along the line
    places = places.order_by("line_location")

    return places


def get_places_within(point, max_distance=100):
    # make range a distance object
    max_d = D(m=max_distance)

    # get places within range
    places = Place.objects.filter(geom__distance_lte=(point, max_d))

    # annotate with distance
    places = places.annotate(distance_from_line=Distance("geom", point))

    # sort by distance
    places = places.order_by("distance_from_line",)

    return places


def get_distances(points):
    """
    Return a list with the distance of each point relative to the previous one in the list.
    """

    def get_relative_distances():
        if points:
            yield 0

        yield from (p2.distance(p1) for p1, p2 in zip(points[1:], points))

    return list(accumulate(get_relative_distances()))
