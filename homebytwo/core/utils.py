from collections import namedtuple
from itertools import chain, islice, tee
from os import path

# named tupple to handle Urls
Link = namedtuple("Link", ["url", "text"])


def get_image_path(instance, filename):
    """
    callable to define the image upload path according
    to the type of object: segment, route, etc.. as well as
    the id of the object.
    """
    return path.join(
        "images", instance.__class__.__name__, str(instance.id), filename
    )


def current_and_next(some_iterable):
    """
    using itertools to make current and next item of an iterable available:
    http://stackoverflow.com/questions/1011938/python-previous-and-next-values-inside-a-loop
    """
    items, nexts = tee(some_iterable, 2)
    nexts = chain(islice(nexts, 1, None), [None])
    return zip(items, nexts)
