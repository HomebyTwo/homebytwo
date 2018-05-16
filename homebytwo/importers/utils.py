from django.contrib import messages
from django.db import IntegrityError, transaction
from django.forms import HiddenInput, modelform_factory, modelformset_factory
from social_core.exceptions import AuthException
from stravalib.client import Client as StravaClient
from stravalib.exc import AccessUnauthorized

from ..routes.forms import RoutePlaceForm
from ..routes.models import Athlete, Place, RoutePlace
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

    # retrieve the athlete from the user
    athlete = Athlete.objects.get(user=user)

    # create the client
    strava_client = StravaClient(access_token=athlete.strava_token)

    # Retrieve athlete from Strava to test the token
    try:
        strava_client.get_athlete()

    # invalid authorization token
    except AccessUnauthorized:

        # erase unauthorized strava token
        athlete.strava_token = None
        athlete.save()

        raise

    return strava_client


def save_strava_token_from_social(backend, user, response, *args, **kwargs):
    """
    Add strava_token to the athlete when djnago social creates a user with Strava

    This pipeline entry recycles the strava access token retrieved
    by Django Social Auth and adds it to the athlete table of the user.
    The user does not need to click on Strava Connect again in order to retrieve Strava Routes.
    """
    if backend.name == 'strava' and kwargs['new_association']:
        athlete, created = Athlete.objects.get_or_create(user=user)
        athlete.strava_token = response.get('access_token')
        athlete.save()


def associate_by_strava_token(backend, details, user=None, *args, **kwargs):
    """
    Associate current auth with a user with the same Strava Token in the DB.

    With this pipeline, we try to find out if a user already exists with
    the retrieved Strava access_token, so that we can associate the auth
    with the user instead of creating a new one.

    """
    if user:
        return None

    access_token = kwargs['response']['access_token']

    if access_token:
        # Try to associate accounts with the same strava token,
        # only if it's a single object. AuthException is raised if multiple
        # objects are returned.
        try:
            athlete = Athlete.objects.get(strava_token=access_token)

        except Athlete.DoesNotExist:
            return None

        except Athlete.MultipleObjectsReturned:
            raise AuthException(
                backend,
                'The given strava token is associated with another account'
            )

        else:
            return {'user': athlete.user,
                    'is_new': False}


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


def get_checkpoints(route):
    """
    retrieve checkpoints within a maximum distance of the route and
    enrich them with information retrieved from the route data.
    """
    places = Place.objects.find_places_along_line(
        route.geom,
        max_distance=75
    )

    # enrich checkpoint data with information
    checkpoints = []

    for place in places:

        altitude_on_route = route.get_distance_data(
            place.line_location, 'altitude')
        place.altitude_on_route = altitude_on_route

        length_from_start = route.get_distance_data(
            place.line_location, 'length')
        place.distance_from_start = length_from_start

        # get cummulative altitude gain
        totalup = route.get_distance_data(
            place.line_location, 'totalup')
        place.totalup = totalup

        # get cummulative altitude loss
        totaldown = route.get_distance_data(
            place.line_location, 'totaldown')
        place.totaldown = totaldown

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
