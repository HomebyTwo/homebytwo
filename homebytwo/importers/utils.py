from django.contrib import messages
from django.db import (
    IntegrityError,
    transaction,
)
from django.forms import (
    HiddenInput,
    modelform_factory,
    modelformset_factory,
)
from social_django.utils import load_strategy
from stravalib.client import Client as StravaClient

from ..routes.forms import RoutePlaceForm
from ..routes.models import (
    Place,
    RoutePlace,
)
from .forms import ImportersRouteForm


class SwitzerlandMobilityError(Exception):
    """
    When the connection to Switzerland Mobility Plus works but the server
    responds with an error code: 404, 500, etc.
    """
    pass


def get_strava_client(user):
    """
    instantiate the Strava client with the athlete's authorization token
    """

    # retrieve the access token from the user with social auth
    social = user.social_auth.get(provider='strava')
    strava_access_token = social.get_access_token(load_strategy())

    # create the Strava client
    strava_client = StravaClient(access_token=strava_access_token)

    return strava_client


def get_route_form(route):
    """
    GET detail view: instanciate route_form with model instance and
    set the query for start and end places.
    """
    RouteForm = modelform_factory(
        type(route),
        form=ImportersRouteForm,
    )

    route_form = RouteForm(
        instance=route,
        prefix='route',
    )

    # find places to display in the select
    # for start, finish points.
    route_form.fields['start_place'].queryset = \
        route.get_closest_places_along_line(
            line_location=0,  # start
            max_distance=200,
    )

    route_form.fields['end_place'].queryset = \
        route.get_closest_places_along_line(
            line_location=1,  # finish
            max_distance=200,
    )

    return route_form


def post_route_form(request, route):
    """
    POST detail view: instanciate route form with POST values.
    """
    RouteForm = modelform_factory(
        type(route),
        form=ImportersRouteForm,
    )

    return RouteForm(
        request.POST,
        prefix='route',
    )


def get_place_type_choices(places_qs):
    """
    limit available place_type filter choices to place_types found in a place querystring.
    takes a Place query string and returns a list of choices to use in the filter configuration.
    """

    # limit place type choices to available ones
    found_place_types = {place.place_type for place in places_qs}

    choices = []

    for key, value in Place.PLACE_TYPE_CHOICES:
        if isinstance(value, (list, tuple)):
            for key2, value2 in value:
                if key2 in found_place_types:
                    choices.append((key2, value2))
        else:
            if key in found_place_types:
                choices.append((key, value))

    return choices


def get_checkpoints(route, filter_qs):
    """
    retrieve checkpoints within a maximum distance of the route and
    enrich them with altitude and distance information retrieved from the route data.
    """
    places = Place.objects.find_places_along_line(route.geom, filter_qs)

    # enrich checkpoint data with information
    checkpoints = []

    for place in places:

        altitude_on_route = route.get_distance_data(
            place.line_location, 'altitude')
        place.altitude_on_route = altitude_on_route

        length_from_start = route.get_distance_data(
            place.line_location, 'length')
        place.distance_from_start = length_from_start

        checkpoints.append(place)

    return checkpoints


def get_route_places_formset(route, checkpoints):
    """
    GET detail view creates a Model Formset populated with all the
    checkpoints found along the route.
    the user can select and save the relevant places to the imported route.

    This is used in both the Strava and Switzerland Mobility
    detail import page.

    """

    # convert checkpoints to RoutePlace objects
    route_places = [
        RoutePlace(
            place=place,
            line_location=place.line_location,
            altitude_on_route=route.get_distance_data(
                place.line_location, 'altitude').m,
        )
        for place in checkpoints
    ]

    # create form class with modelformset_factory
    RoutePlaceFormset = modelformset_factory(
        RoutePlace,
        form=RoutePlaceForm,
        extra=len(route_places),
        widgets={
            'place': HiddenInput,
            'line_location': HiddenInput,
            'altitude_on_route': HiddenInput,
        }
    )

    # instantiate form with initial data
    return RoutePlaceFormset(
        prefix='places',
        queryset=RoutePlace.objects.none(),
        initial=[
            {
                'place': route_place.place,
                'line_location': route_place.line_location,
                'altitude_on_route': route_place.altitude_on_route,
            }
            for route_place in route_places
        ],
    )


def post_route_places_formset(request, route):
    """
    POST detail view: return the route_places model_formset
    populated with POST data.
    """
    # create form class with modelformset_factory
    RoutePlaceFormset = modelformset_factory(
        RoutePlace,
        form=RoutePlaceForm,
        widgets={
            'place': HiddenInput,
            'line_location': HiddenInput,
            'altitude_on_route': HiddenInput,
        }
    )

    return RoutePlaceFormset(
        request.POST,
        prefix='places',
    )


def save_detail_forms(request, route_form, route_places_formset):
    """
    POST detail view: if the forms validate, try to save the routes
    and route places.
    """
    # validate places form and return errors if any
    if not route_places_formset.is_valid():
        for error in route_places_formset.errors:
            messages.error(request, error)
        return False

    # validate route form and return errors if any
    if not route_form.is_valid():
        for error in route_form.errors:
            messages.error(request, error)
        return False

    # create the route with the route_form
    new_route = route_form.save(commit=False)
    # set user for route
    new_route.owner = request.user

    try:
        with transaction.atomic():
            # save the route
            new_route.save()

            # create the route places from the route_place_forms
            for form in route_places_formset:
                if form.cleaned_data['include']:
                    route_place = form.save(commit=False)
                    route_place.route = new_route
                    route_place.save()

    except IntegrityError as error:
        message = 'Integrity Error: {}. '.format(error)
        messages.error(request, message)
        return False

    return new_route
