from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from requests.exceptions import ConnectionError
from stravalib.client import Client as StravaClient
from stravalib.exc import AccessUnauthorized

from ..routes.models import Athlete
from .decorators import strava_required, switerland_mobility_required
from .forms import SwitzerlandMobilityLogin
from .models import StravaRoute, SwitzerlandMobilityRoute
from .utils import (SwitzerlandMobilityError, get_route_form,
                    get_checkpoints_formset, get_strava_client,
                    post_route_form, post_checkpoints_formset,
                    save_detail_forms)

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

    template = 'importers/routes.html'
    context = {'source': STRAVA_SOURCE_INFO}

    try:
        strava_client = get_strava_client(request.user)

    except ConnectionError as error:
        message = "Could not connect to Strava: {}".format(error)
        messages.error(request, message)
        return render(request, template, context)

    except AccessUnauthorized:
        message = ('Strava Authorization refused. Try connect to Strava again')
        messages.error(request, message)
        return redirect('strava_connect')

    # Retrieve routes from Strava
    new_routes, old_routes = StravaRoute.objects.get_routes_list_from_server(
        user=request.user,
        strava_client=strava_client
    )

    context.update({
        'new_routes': new_routes,
        'old_routes': old_routes,
    })

    return render(request, template, context)


@login_required
@strava_required
def strava_route(request, source_id):
    """
    Detail view to import a route from Strava.
    """

    # default values for variables passed to the request context
    checkpoints_forms = False
    route_form = False
    checkpoints_formset = False

    # model instance from source_id
    route = StravaRoute(source_id=source_id)

    # with a POST request try to save route and places
    if request.method == 'POST':

        # populate route_form with POST data
        route_form = post_route_form(request, route)

        # populate the checkpoints_formset with POST data
        checkpoints_formset = post_checkpoints_formset(request, route)

        # validate forms and save the route and places
        new_route = save_detail_forms(
            request,
            route_form,
            checkpoints_formset
        )

        # Success! redirect to the page of the newly imported route
        if new_route:
            message = 'Route imported successfully from Strava'
            messages.success(request, message)
            return redirect('routes:route', pk=new_route.id)

    if request.method == 'GET':

        # get route details from Strava API
        strava_client = get_strava_client(request.user)
        route.get_route_details(strava_client)

        # add user information to route.
        # to check if the route has already been imported.
        route.owner = request.user

        # populate the route_form with route details
        route_form = get_route_form(route)

        # get checkpoints along the way
        checkpoints = route.find_checkpoints()

        # get form to save places along the route
        checkpoints_formset = get_checkpoints_formset(route, checkpoints)

        # prepare zipped list for the template
        checkpoints_forms = zip(checkpoints, checkpoints_formset.forms)

    context = {
        'route': route,
        'route_form': route_form,
        'checkpoints_forms': checkpoints_forms,
        'places_form': checkpoints_formset,
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

    try:
        new_routes, old_routes = manager.get_remote_routes(
            request.session,
            request.user,
        )

    except ConnectionError as error:
        messages.error(request, error)
        new_routes, old_routes = None, None

    except SwitzerlandMobilityError as error:
        messages.error(request, error)
        new_routes, old_routes = None, None

    template = 'importers/routes.html'
    context = {
        'source': SWITZERLAND_MOBILITY_SOURCE_INFO,
        'new_routes': new_routes,
        'old_routes': old_routes,
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
    checkpoints_forms = []
    route_form = False
    checkpoints_formset = False

    # model instance with source_id
    route = SwitzerlandMobilityRoute(source_id=source_id)

    # with a POST request try to save route and places
    if request.method == 'POST':

        # populate the route_form with POST data
        route_form = post_route_form(request, route)

        # populate the checkpoints_formset with POST data
        checkpoints_formset = post_checkpoints_formset(request, route)

        # validate forms and save the route and places
        new_route = save_detail_forms(
            request,
            route_form,
            checkpoints_formset
        )

        # Success! redirect to the page of the newly imported route
        if new_route:
            message = 'Route imported successfully from Switzerland Mobility'
            messages.success(request, message)
            return redirect('routes:route', pk=new_route.id)

    # GET request
    if request.method == 'GET':

        # fetch route details from Switzerland Mobility
        try:
            route.get_route_details()

        except ConnectionError as error:
            messages.error(request, error)

        except SwitzerlandMobilityError as error:
            messages.error(request, error)

        # no exception
        else:
            # add user to check if route has already been imported
            route.owner = request.user

            # populate the route_form with route details
            route_form = get_route_form(route)

            # find checkpoints along the route
            checkpoints = route.find_checkpoints()

            # get formset to save checkpoints
            checkpoints_formset = get_checkpoints_formset(route, checkpoints)

            # arrange places and formsets for template
            checkpoints_forms = zip(checkpoints, checkpoints_formset.forms)

    context = {
        'route': route,
        'route_form': route_form,
        'checkpoints_forms': checkpoints_forms,
        'checkpoints_formset': checkpoints_formset,
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
            cookies = form.retrieve_authorization_cookie(request)

            # cookies retrieved successfully
            if cookies:
                # add cookies to the user session
                request.session['switzerland_mobility_cookies'] = cookies
                # redirect to the route list
                return redirect('switzerland_mobility_routes')

        # something went wrong, render the login page,
        # errors handled in messages
        context = {'form': form}
        return render(request, template, context)

    # GET request, print the form
    else:
        form = SwitzerlandMobilityLogin()
        context = {'form': form}
        return render(request, template, context)
