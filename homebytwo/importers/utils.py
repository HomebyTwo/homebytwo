from django.http import Http404

from requests import Session, codes
from requests.exceptions import ConnectionError

from ..routes.models import Route
from .exceptions import SwitzerlandMobilityError, SwitzerlandMobilityMissingCredentials


def request_json(url, cookies=None):
    """
    Makes a get call to an url to retrieve a json from Switzerland Mobility
    while trying to handle server and connection errors.
    """
    with Session() as session:
        try:
            response = session.get(url, cookies=cookies)

        # connection error and inform the user
        except ConnectionError:
            message = "Connection Error: could not connect to {url}. "
            raise ConnectionError(message.format(url=url))

        else:
            # if request is successful return json object
            if response.status_code == codes.ok:
                json = response.json()
                return json

            # client error: access denied
            if response.status_code == 403:
                message = "We could not import this route. "

                # athlete is logged-in to Switzerland Mobility
                if cookies:
                    message += (
                        "Ask the route creator to share it"
                        "publicly on Switzerland Mobility. "
                    )
                    raise SwitzerlandMobilityError(message)

                # athlete is not logged-in to Switzerland Mobility
                else:
                    message += (
                        "If you are the route creator, try logging-in to"
                        "Switzerland mobility. If the route is not yours,"
                        "ask the creator to share it publicly. "
                    )
                    raise SwitzerlandMobilityMissingCredentials(message)

            # server error: display the status code
            else:
                message = "Error {code}: could not retrieve information from {url}"
                raise SwitzerlandMobilityError(
                    message.format(code=response.status_code, url=url)
                )


def split_routes(remote_routes, local_routes):
    """
    splits the list of remote routes in  3 groups: new, existing and deleted
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


def get_proxy_class_from_data_source(data_source):
    """
    retrieve route proxy class from "data source" value in the url or raise 404
    """
    route_class = Route(data_source=data_source).proxy_class

    if route_class is None:
        raise Http404("Data Source does not exist")
    else:
        return route_class
