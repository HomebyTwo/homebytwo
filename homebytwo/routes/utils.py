from itertools import chain, tee, islice

from django.contrib.gis.db.models.functions import Distance, LineLocatePoint
from django.contrib.gis.measure import D

from .models import Place


def create_segments_from_checkpoints(checkpoints, start=0, end=1):
    """
    returns a list of segments as tuples with start and end locations
    along the original line.

    """

    # sorted list of line_locations from the list of places as
    # well as the start and the end location of the segment where
    # the places were found.
    line_locations = chain(
        [start],
        [checkpoint.line_location for checkpoint in checkpoints],
        [end]
    )

    # use the custom iterator, exclude segments where start and end
    # locations are the same. Also exclude segment where 'nxt == None`.
    segments = [(crt, nxt) for crt, nxt
                in current_and_next(line_locations)
                if crt != nxt and nxt]

    return segments


def current_and_next(some_iterable):
    """
    using itertools to make current and next item of an iterable available:
    http://stackoverflow.com/questions/1011938/python-previous-and-next-values-inside-a-loop
    """
    items, nexts = tee(some_iterable, 2)
    nexts = chain(islice(nexts, 1, None), [None])
    return zip(items, nexts)


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
    places = places.annotate(distance_from_line=Distance('geom', line))

    # annotate with location along the line between 0 and 1
    places = places.annotate(line_location=LineLocatePoint(line, 'geom'))

    # remove start and end places within 1% of start and end location
    places = places.filter(
        line_location__gt=0.01,
        line_location__lt=0.99,
    )

    places = places.order_by('line_location')

    return places


def get_places_within(point, max_distance=100):
    # make range a distance object
    max_d = D(m=max_distance)

    # get places within range
    places = Place.objects.filter(geom__distance_lte=(point, max_d))

    # annotate with distance
    places = places.annotate(distance_from_line=Distance('geom', point))

    # sort by distance
    places = places.order_by('distance_from_line',)

    return places
