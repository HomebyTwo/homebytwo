from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render

from requests.exceptions import ConnectionError
from stravalib.exc import AccessUnauthorized

from ..routes.forms import RouteForm
from .forms import SwitzerlandMobilityLogin
from .models import StravaRoute, SwitzerlandMobilityRoute
from .utils import SwitzerlandMobilityError, save_detail_forms

DATA_SOURCE_CLASSES = {
    "strava": StravaRoute,
    "switzerland_mobility": SwitzerlandMobilityRoute,
}


def get_route_class_from_data_source(request, data_source):
    """
    retrieve route class from "data source" value in the url or raise 404
    """
    route_class = DATA_SOURCE_CLASSES.get(data_source)
    if route_class:
        # check if user has access credentials
        route_class.objects.check_user_credentials(request)
        return route_class
    else:
        raise Http404("Data Source does not exist")


@login_required
def index(request):
    return render(request, "importers/index.html")


@login_required
def strava_connect(request):
    return render(request, "importers/strava/connect.html")


@login_required
def import_routes(request, data_source):
    """
    retrieve the athlete's list of routes on Strava
    """

    template = "importers/routes.html"

    # retrieve route class from data source in url
    route_class = get_route_class_from_data_source(request, data_source)

    # retrieve remote routes list
    try:
        remote_routes = route_class.objects.get_remote_routes_list(
            athlete=request.user.athlete, session=request.session
        )

    except ConnectionError as error:
        message = "Could not connect to Strava: {}".format(error)
        messages.error(request, message)
        remote_routes = []

    except SwitzerlandMobilityError as error:
        messages.error(request, error)
        remote_routes = []

    except AccessUnauthorized:
        message = "Strava Authorization refused. Try to connect to Strava again"
        messages.error(request, message)
        return redirect("strava_connect")

    # retrieve the athlete's list of routes already saved in homebytwo
    local_routes = route_class.objects.for_user(request.user)

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

    context = {
        "new_routes": new_routes,
        "existing_routes": existing_routes,
        "deleted_routes": deleted_routes,
        "data_source_name": route_class.DATA_SOURCE_NAME,
        "data_source_link": route_class.DATA_SOURCE_LINK,
    }

    return render(request, template, context)


@login_required
def import_route(request, data_source, source_id):
    """
    import form for Strava

    There is a modelform for the route with custom __init__ ans save methods
    to find available checkpoints and save the ones selected by the athlete
    to the route.
    """

    # retrieve route class from data source in url
    route_class = get_route_class_from_data_source(request, data_source)

    # instantiate route stub with athlte ans source_id from url
    route = route_class(athlete=request.user.athlete, source_id=source_id)

    # fetch route details from Remote API
    try:
        route.get_route_details()

    except ConnectionError as error:
        message = "Could not connect to the remote server: {}".format(error)
        messages.error(request, message)

    except AccessUnauthorized:
        message = "Strava Authorization refused. Try to connect to Strava again"
        messages.error(request, message)
        return redirect("strava_connect")

    except SwitzerlandMobilityError as error:
        message = "Error connecting to Switzerland Mobility Plus: {}".format(error)
        messages.error(request, message)

    if request.method == "POST":

        # populate checkpoints_formset with POST data
        route_form = RouteForm(request.POST, instance=route)

        # validate forms and save the route and places
        new_route = save_detail_forms(request, route_form)

        # Success! redirect to the page of the newly imported route
        if new_route:
            message = "Route imported successfully from {}".format(
                route_class.DATA_SOURCE_NAME
            )
            messages.success(request, message)
            return redirect("routes:route", pk=new_route.id)

    if request.method == "GET":

        # populate the route_form with route details
        route, exists = route.refresh_from_db_if_exists()
        route_form = RouteForm(instance=route)

    context = {
        "route": route,
        "form": route_form,
    }

    template = "routes/route_form.html"

    return render(request, template, context)


@login_required
def switzerland_mobility_login(request):
    template = "importers/switzerland_mobility/login.html"

    # POST request, validate and login
    if request.method == "POST":

        # instanciate login form and populate it with POST data:
        form = SwitzerlandMobilityLogin(request.POST)

        # If the form validates,
        # try to retrieve the Switzerland Mobility cookies
        if form.is_valid():
            cookies = form.retrieve_authorization_cookie(request)

            # cookies retrieved successfully
            if cookies:
                # add cookies to the user session
                request.session["switzerland_mobility_cookies"] = cookies
                # redirect to the route list
                return redirect("switzerland_mobility_routes")

        # something went wrong, render the login page,
        # errors handled in messages
        context = {"form": form}
        return render(request, template, context)

    # GET request, print the form
    else:
        form = SwitzerlandMobilityLogin()
        context = {"form": form}
        return render(request, template, context)
