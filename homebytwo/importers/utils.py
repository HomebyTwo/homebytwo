from django.contrib import messages
from django.db import IntegrityError

from requests import Session, codes
from requests.exceptions import ConnectionError


class SwitzerlandMobilityError(Exception):
    """
    When the connection to Switzerland Mobility Plus works but the server
    responds with an error code: 404, 500, etc.
    """

    pass


def request_json(url, cookies=None):
    """
    Makes a get call to an url to retrieve a json
    while managing server and connection errors.
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
