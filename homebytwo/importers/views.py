from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.db import IntegrityError, transaction
from django.forms import HiddenInput, modelform_factory, modelformset_factory
from django.http import HttpResponseRedirect
from django.shortcuts import render
from stravalib.client import Client as StravaClient

from ..routes.forms import RoutePlaceForm
from ..routes.models import Athlete, Place, RoutePlace
from .forms import ImportersRouteForm, SwitzerlandMobilityLogin
from .models import StravaRoute, SwitzerlandMobilityRoute

# Switzerland Mobility info for the templates.
SWITZERLAND_MOBILITY_SOURCE_INFO = {
    'name': 'Switzerland Mobility Plus',
    'svg': 'images/switzerland_mobility.svg',
    'muted_svg': 'images/switzerland_mobility_muted.svg',
    'route_view': 'switzerland_mobility_route',
    'routes_view': 'switzerland_mobility_routes',
}

# Strava info for templates.
STRAVA_SOURCE_INFO = {
    'name': 'Strava',
    'svg': 'images/strava.svg',
    'muted_svg': 'images/strava_muted.svg',
    'route_view': 'strava_route',
    'routes_view': 'strava_routes',
}


@login_required
def index(request):
    return render(request, 'importers/index.html')


@login_required
def strava_connect(request):
    """
    generate the Strava connect button.
    """
    # Initialize stravalib client
    strava_client = StravaClient()

    # generate the absolute redirect url
    redirect_url = reverse('strava_authorized')
    absolute_redirect_url = request.build_absolute_uri(redirect_url)

    # Generate Strava authorization URL
    strava_authorize_url = strava_client.authorization_url(
        client_id=settings.STRAVA_CLIENT_ID,
        redirect_uri=absolute_redirect_url,
    )

    context = {
        'strava_authorize_url': strava_authorize_url,
    }

    # Render the Strava connect button
    return render(request, 'importers/strava/connect.html', context)


@login_required
def strava_authorized(request):
    # Initialize stravalib client
    strava_client = StravaClient()

    # Obtain access token
    code = request.GET.get('code', '')
    access_token = strava_client.exchange_code_for_token(
                        client_id=settings.STRAVA_CLIENT_ID,
                        client_secret=settings.STRAVA_CLIENT_SECRET,
                        code=code,
                    )

    # Save access token to athlete
    _set_strava_token(request.user, access_token)

    # redirect to the Strava routes page
    redirect_url = reverse('strava_routes')
    return HttpResponseRedirect(redirect_url)


@login_required
def strava_routes(request):

    # find or create the athlete related to the user
    athlete, created = Athlete.objects.get_or_create(user=request.user)

    # if user has no token, redirect to Strava connect
    if not athlete.strava_token:
        redirect_url = reverse('strava_connect')
        return HttpResponseRedirect(redirect_url)

    # create the client
    strava_client = StravaClient(access_token=athlete.strava_token)

    # Retrieve athlete from Strava
    try:
        strava_athlete = strava_client.get_athlete()
    except:
        raise

    # Retrieve routes from Strava
    new_routes, old_routes = StravaRoute.objects. \
        get_routes_list_from_server(
            user=request.user,
            strava_client=strava_client
        )

    context = {
        'source': STRAVA_SOURCE_INFO,
        'strava_athlete': strava_athlete,
        'new_routes': new_routes,
        'old_routes': old_routes,
    }

    template = 'importers/routes.html'

    return render(request, template, context)


@login_required
def strava_route(request, source_id):
    """
    Detail view to import a route from Strava.
    """

    # default values for variables passed to the request context
    places = False
    route_form = False
    route_places_formset = False
    response = {
        'error': False,
        'message': '',
    }

    # model instance from source_id
    route = StravaRoute(source_id=int(source_id))

    if request.method == 'POST':

        # populate route_form with POST data
        route_form = _post_route_form(request, route)

        # populate the route_places_formset with POST data
        route_places_formset = _post_route_places_formset(request, route)

        # validate forms and save the route and places
        if not response['error']:
            new_route, response = _save_detail_forms(
                request,
                response,
                route_form,
                route_places_formset
            )

        # Success! redirect to the page of the newly imported route
        if not response['error']:
            redirect_url = reverse('routes:route', args=(new_route.id,))
            return HttpResponseRedirect(redirect_url)

    if request.method == 'GET':

        # find or create the athlete related to the user
        athlete, created = Athlete.objects.get_or_create(user=request.user)

        # if user has no token, redirect to Strava connect
        if not athlete.strava_token:
            redirect_url = reverse('strava_connect')
            return HttpResponseRedirect(redirect_url)

        # create the client
        strava_client = StravaClient(access_token=athlete.strava_token)

        # get route details from Strava API
        route.get_route_details(strava_client)

        # add user information to route.
        # to check if the route has already been imported.
        route.user = request.user

        # populate the route_form with route details
        route_form = _get_route_form(route)

        # get checkpoints along the way
        checkpoints = _get_checkpoints(route)

        # get form to save places along the route
        route_places_formset = _get_route_places_formset(route, checkpoints)

        # prepare zipped list for the template
        places = zip(checkpoints, route_places_formset.forms)

    context = {
        'response': response,
        'route': route,
        'route_form': route_form,
        'places': places,
        'places_form': route_places_formset,
        'source': STRAVA_SOURCE_INFO
    }

    template = 'importers/route.html'

    return render(request, template, context)


@login_required
def switzerland_mobility_routes(request):
    # Check if logged-in to Switzeland Mobility
    try:
        request.session['switzerland_mobility_cookies']

    # No login cookies
    except KeyError:
        # redirect to the switzeland mobility login page
        redirect_url = reverse('switzerland_mobility_login')
        return HttpResponseRedirect(redirect_url)

    # Retrieve remote routes from Switzerland Mobility
    manager = SwitzerlandMobilityRoute.objects
    new_routes, old_routes, response = manager.get_remote_routes(
        request.session, request.user)

    template = 'importers/routes.html'
    context = {
        'source': SWITZERLAND_MOBILITY_SOURCE_INFO,
        'new_routes': new_routes,
        'old_routes': old_routes,
        'response': response,
    }

    return render(request, template, context)


@login_required
def switzerland_mobility_route(request, source_id):
    """
    Main import page for Switzerland Mobility.
    There is a modelform for the route and a modelformset
    for the places found along the route.

    The route form is instanciated with the json data retrieved from
    Switzerland Mobility.

    The places_form is populated with places found along the retrieved route
    using a query to the database.
    """

    # default values for variables passed to the request context
    places = []
    route_form = False
    route_places_formset = False
    response = {
        'error': False,
        'message': '',
    }

    # model instance with source_id
    route = SwitzerlandMobilityRoute(source_id=int(source_id))

    # with a POST request try to import route and places
    if request.method == 'POST':

        # populate the route_form with POST data
        route_form = _post_route_form(request, route)

        # populate the route_places_formset with POST data
        route_places_formset = _post_route_places_formset(request, route)

        # validate forms and save the route and places
        if not response['error']:
            new_route, response = _save_detail_forms(
                request,
                response,
                route_form,
                route_places_formset
            )

        # Success! redirect to the page of the newly imported route
        if not response['error']:
            redirect_url = reverse('routes:route', args=(new_route.id,))
            return HttpResponseRedirect(redirect_url)

    # GET request
    if request.method == 'GET':

        # fetch route details from Switzerland Mobility
        response = route.get_route_details()

        # route details succesfully retrieved
        if not response['error']:

            # add user to check if route has already been imported
            route.user = request.user

            # populate the route_form with route details
            route_form = _get_route_form(route)

            # find checkpoints along the route
            checkpoints = _get_checkpoints(route)

            # get form set to save route places
            route_places_formset = _get_route_places_formset(
                route,
                checkpoints
            )

            places = zip(checkpoints, route_places_formset.forms)

    context = {
        'response': response,
        'route': route,
        'route_form': route_form,
        'places': places,
        'places_form': route_places_formset,
        'source': SWITZERLAND_MOBILITY_SOURCE_INFO
    }

    template = 'importers/route.html'

    return render(request, template, context)


@login_required
def switzerland_mobility_login(request):
    template = 'importers/switzerland_mobility/login.html'

    # POST request, validate and login
    if request.method == 'POST':

        # instanciate login form and populate it with POST data:
        form = SwitzerlandMobilityLogin(request.POST)

        # If the form validates,
        # try to retrieve the Switzerland Mobility cookies
        if form.is_valid():
            cookies, response = form.retrieve_authorization_cookie()

            # cookies retrieved successfully
            if not response['error']:
                # add cookies to the user session
                request.session['switzerland_mobility_cookies'] = cookies
                # redirect to the route list
                redirect_url = reverse('switzerland_mobility_routes')
                return HttpResponseRedirect(redirect_url)
            # something went wrong, render the login page with the error
            else:
                context = {
                    'form': form,
                    'error': response['error'],
                    'message': response['message'],
                }
                return render(request, template, context)

        # form validation error, render the page with the errors
        else:
            error = True
            message = 'An error has occured. '

            for error in form.errors:
                message += error + ': '
                for error_message in form.errors[error]:
                    message += error_message
            context = {
                'form': form,
                'error': response['error'],
                'message': response['message'],
            }
            return render(request, template, context)

    # GET request, print the form
    else:
        form = SwitzerlandMobilityLogin()
        context = {'form': form}
        return render(request, template, context)


def _set_strava_token(user, token):
    # find or create the athlete related to the user
    athlete, created = Athlete.objects.get_or_create(user=user)

    # save the token to the athlete
    athlete.strava_token = token
    athlete.save()


def _get_route_form(route):
    """
    GET detail view: instanciate route_form with model instance and
    set he query for start and end places.
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


def _post_route_form(request, route):
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


def _get_checkpoints(route):
    """
    retrieve checkpoints within 50m of the route and
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


def _get_route_places_formset(route, checkpoints):
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


def _post_route_places_formset(request, route):
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


def _save_detail_forms(request, response, route_form, route_places_formset):
    """
    POST detail view: if the forms validate, try to save the routes
    and route places.
    """
    # validate places form and return errors if any
    if not route_places_formset.is_valid():
        response['error'] = True
        response['message'] += str(route_places_formset.errors)

    # validate route form and return errors if any
    if not route_form.is_valid():
        response['error'] = True
        response['message'] += str(route_form.errors)

    if response['error']:
        return False, response

    # create the route with the route_form
    new_route = route_form.save(commit=False)
    # set user for route
    new_route.user = request.user
    # calculate time schedule
    new_route.calculate_projected_time_schedule(request.user)

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
        response = {
            'error': True,
            'message': 'Integrity Error: %s. ' % error,
        }

    return new_route, response
