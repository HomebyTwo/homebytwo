from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from stravalib.client import Client as StravaClient

from ..routes.models import Athlete
from .decorators import strava_required, switerland_mobility_required
from .forms import SwitzerlandMobilityLogin
from .models import StravaRoute, SwitzerlandMobilityRoute
from .utils import (
    get_checkpoints, get_route_form, get_route_places_formset,
    get_strava_client, post_route_form, post_route_places_formset,
    save_detail_forms
)

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
    generate the Strava connect button to request the Strava
    authorization token from the user.

    clicking on this button opens an authorization request on strava.com

    accepting takes the user back to the 'strava_authorized' view that
    saves the token.
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
    athlete, created = Athlete.objects.get_or_create(user=request.user)
    athlete.strava_token = access_token
    athlete.save()

    # redirect to the Strava routes page
    return redirect('strava_routes')


@login_required
@strava_required
def strava_routes(request):

    strava_client = get_strava_client(request.user)

    # Retrieve routes from Strava
    new_routes, old_routes = StravaRoute.objects.get_routes_list_from_server(
        user=request.user,
        strava_client=strava_client
    )

    context = {
        'source': STRAVA_SOURCE_INFO,
        'new_routes': new_routes,
        'old_routes': old_routes,
    }

    template = 'importers/routes.html'

    return render(request, template, context)


@login_required
@strava_required
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
    route = StravaRoute(source_id=source_id)

    if request.method == 'POST':

        # populate route_form with POST data
        route_form = post_route_form(request, route)

        # populate the route_places_formset with POST data
        route_places_formset = post_route_places_formset(request, route)

        # validate forms and save the route and places
        if not response['error']:
            new_route, response = save_detail_forms(
                request,
                response,
                route_form,
                route_places_formset
            )

        # Success! redirect to the page of the newly imported route
        if not response['error']:
            return redirect('routes:route', pk=new_route.id)

    if request.method == 'GET':

        # get the strava the client
        strava_client = get_strava_client(request.user)

        # get route details from Strava API
        route.get_route_details(strava_client)

        # add user information to route.
        # to check if the route has already been imported.
        route.user = request.user

        # populate the route_form with route details
        route_form = get_route_form(route)

        # get checkpoints along the way
        checkpoints = get_checkpoints(route)

        # get form to save places along the route
        route_places_formset = get_route_places_formset(route, checkpoints)

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
@switerland_mobility_required
def switzerland_mobility_routes(request):
    """
    retrieve the list of Switzerland Mobility Plus routes
    for the user.
    """
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
        route_form = post_route_form(request, route)

        # populate the route_places_formset with POST data
        route_places_formset = post_route_places_formset(request, route)

        # validate forms and save the route and places
        if not response['error']:
            new_route, response = save_detail_forms(
                request,
                response,
                route_form,
                route_places_formset
            )

        # Success! redirect to the page of the newly imported route
        if not response['error']:
            return redirect('routes:route', pk=new_route.id)

    # GET request
    if request.method == 'GET':

        # fetch route details from Switzerland Mobility
        response = route.get_route_details()

        # route details succesfully retrieved
        if not response['error']:

            # add user to check if route has already been imported
            route.user = request.user

            # populate the route_form with route details
            route_form = get_route_form(route)

            # find checkpoints along the route
            checkpoints = get_checkpoints(route)

            # get form set to save route places
            route_places_formset = get_route_places_formset(
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
                return redirect('switzerland_mobility_routes')

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
