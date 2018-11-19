from django.contrib import messages
from django.db import IntegrityError, transaction
from django.forms import modelform_factory
from social_core.exceptions import AuthException
from stravalib.client import Client as StravaClient
from stravalib.exc import AccessUnauthorized

from ..routes.models import Athlete, Place, RoutePlace
from .filters import PlaceFilter
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


def post_route_form(request, route):
    """
    POST a RouteForm passing the route class along:
    SwitzerlandMobilityRoute or Strava
    """
    RouteForm = modelform_factory(
        type(route),
        form=ImportersRouteForm,
    )

    return RouteForm(request.POST)


def get_place_filter(route, request):

    def get_place_type_choices(places_qs):
        """
        return place_type choices for the types found in a place query set.
        Takes a Place query string and returns a list of choices used
        in the filter configuration.
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

    # initial queryset
    places_qs = Place.objects.locate_places_on_line(route.geom, 75)

    # retrieve available types for all checkpoints
    place_type_choices = get_place_type_choices(places_qs)

    # filter bus stops for bike routes
    if route.activity_type == 'Bike':
        places_qs = places_qs.exclude(place_type=Place.BUS_STATION)

    # define place_type filter object
    place_filter = PlaceFilter(
        request.GET,
        queryset=places_qs
    )

    # set choices for the filter
    place_filter.form.fields['place_type'].choices = place_type_choices

    return place_filter


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


def save_detail_forms(request, route_form, route):
    """
    If the route form validates, try to save the route places.
    """

    # validate route form and return errors if any
    if not route_form.is_valid():
        for error in route_form.errors:
            messages.error(request, error)
        return False

    # create the route with the route_form
    new_route = route_form.save(commit=False)

    # set user for route
    new_route.owner = request.user

    # try to the route alongside all route places
    try:
        with transaction.atomic():

            # save the route
            new_route.save()

            # save the individual RoutePlace objects passed by the form
            # as `id_linelocation`
            for place in request.POST.getlist('places'):

                # separate the place_id from the line_locations
                place_id, line_location = place.split('_')

                # calculate altitude on route
                altitude_on_route = new_route.get_distance_data(
                    float(line_location),
                    'altitude',
                )

                RoutePlace.objects.create(
                    route=new_route,
                    place=Place.objects.get(pk=place_id),
                    line_location=float(line_location),
                    altitude_on_route=altitude_on_route.m,
                )

    except IntegrityError as error:
        message = 'Integrity Error: {}. '.format(error)
        messages.error(request, message)
        return False

    return new_route
