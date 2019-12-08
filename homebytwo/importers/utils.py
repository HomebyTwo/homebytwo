from django.contrib import messages
from django.db import IntegrityError
from django.http import Http404

from requests import Session, codes
from requests.exceptions import ConnectionError

from ..routes.models import Route
from .exceptions import SwitzerlandMobilityError


def request_json(url, cookies=None):
    """
    Makes a get call to an url to retrieve a json from Switzerland Mobility
    while trying to handle server and connection errors.
    """
    with Session() as session:
        try:
            request = session.get(url, cookies=cookies)

        # connection error and inform the user
        except ConnectionError:
            message = "Connection Error: could not connect to {0}. "
            raise ConnectionError(message.format(url))

        else:
            # if request is successful return json object
            if request.status_code == codes.ok:
                json = request.json()
                return json

            # server error: display the status code
            else:
                message = "Error {0}: could not retrieve information from {1}"
                raise SwitzerlandMobilityError(message.format(request.status_code, url))


def save_detail_forms(request, route_form):
    """
    POST detail view: if the forms validate, try to save the routes
    and route places.
    """

    # validate route form and return errors if any
    if not route_form.is_valid():
        for error in route_form.errors:
            messages.error(request, error)
        return False

    try:
        return route_form.save()

    except IntegrityError as error:
        message = "Integrity Error: {}. ".format(error)
        messages.error(request, message)
        return False


def split_routes(remote_routes, local_routes):
    """
    splits the list of remote routes in  3 groups: new, existiing and deleted
    """

    # routes in remote service but not in homebytwo
    new_routes = [
        remote_route
        for remote_route in remote_routes
        if remote_route.source_id
        not in [local_route.source_id for local_route in local_routes]
    ]

    # routes in both remote service and homebytwo
    existing_routes = [
        local_route
        for local_route in local_routes
        if local_route.source_id
        in [remote_route.source_id for remote_route in remote_routes]
    ]

    # routes in homebytwo but deleted in remote service
    deleted_routes = [
        local_route
        for local_route in local_routes
        if local_route.source_id
        not in [remote_route.source_id for remote_route in remote_routes]
    ]

    return new_routes, existing_routes, deleted_routes


def get_route_class_from_data_source(request, data_source):
    """
    retrieve route class from "data source" value in the url or raise 404
    """
    try:
        route_class = Route(data_source=data_source).proxy_class
    except KeyError:
        raise Http404("Data Source does not exist")
    else:
        return route_class
