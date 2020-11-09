from pathlib import Path

from django.forms import model_to_dict

from homebytwo.routes.forms import RouteForm
from homebytwo.routes.models import Place
from homebytwo.routes.tests.factories import PlaceFactory, RouteFactory


def open_data(file, dir_path, binary=True):
    data_dir = Path("data")
    path = dir_path / data_dir / file

    if binary:
        return open(path, "rb")
    else:
        return open(path)


def read_data(file, dir_path=Path(__file__).resolve().parent, binary=False):
    return open_data(file, dir_path, binary).read()


def create_checkpoints_from_geom(geom, number_of_checkpoints):
    checkpoints_data = []
    endpoint = number_of_checkpoints + 1
    for index in range(1, endpoint):
        line_location = index / endpoint
        place = PlaceFactory(geom=geom.interpolate_normalized(line_location))
        checkpoints_data.append("_".join([str(place.id), str(line_location)]))

    return checkpoints_data


def create_route_with_checkpoints(number_of_checkpoints, *args, **kwargs):
    route = RouteFactory(*args, **kwargs)
    checkpoints_data = create_checkpoints_from_geom(route.geom, number_of_checkpoints)
    for checkpoint_data in checkpoints_data:
        pk, line_location = checkpoint_data.split("_")
        place = Place.objects.get(pk=pk)
        route.places.add(
            place, through_defaults={"line_location": line_location}
        )
    return route


def get_route_post_data(route, activity_type=1):
    post_data = {"activity_type": activity_type}
    for key, value in model_to_dict(route, fields=RouteForm.Meta.fields).items():
        if value:
            post_data[key] = value
    return post_data
