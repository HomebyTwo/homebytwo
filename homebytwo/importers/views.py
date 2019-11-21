from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from requests.exceptions import ConnectionError
from stravalib.exc import AccessUnauthorized

from .decorators import strava_required, switerland_mobility_required
from .forms import ImportersRouteForm, SwitzerlandMobilityLogin
from .models import StravaRoute, SwitzerlandMobilityRoute
from .utils import SwitzerlandMobilityError, post_route_form, save_detail_forms

# Switzerland Mobility info for the templates.
SWITZERLAND_MOBILITY_SOURCE_INFO = {
    "name": "Switzerland Mobility Plus",
    "svg": "images/switzerland_mobility.svg",
    "muted_svg": "images/switzerland_mobility_muted.svg",
    "route_view": "switzerland_mobility_route",
    "routes_view": "switzerland_mobility_routes",
}

# Strava info for templates.
STRAVA_SOURCE_INFO = {
    "name": "Strava",
    "svg": "images/strava.svg",
    "muted_svg": "images/strava_muted.svg",
    "route_view": "strava_route",
    "routes_view": "strava_routes",
}


@login_required
def index(request):
    return render(request, "importers/index.html")


@login_required
def strava_connect(request):
    return render(request, "importers/strava/connect.html")


@login_required
@strava_required
def strava_routes(request):
    """
    retrieve the athlete's list of routes on Strava
    """

    template = "importers/routes.html"

    # retrieve remote routes list
    try:
        new_routes, old_routes = StravaRoute.objects.get_routes_list_from_server(
            athlete=request.user.athlete
        )

    except ConnectionError as error:
        message = "Could not connect to Strava: {}".format(error)
        messages.error(request, message)
        new_routes, old_routes = [], []

    except AccessUnauthorized:
        message = "Strava Authorization refused. Try to connect to Strava again"
        messages.error(request, message)
        return redirect("strava_connect")

    context = {
        "source": STRAVA_SOURCE_INFO,
        "new_routes": new_routes,
        "old_routes": old_routes
    }

    return render(request, template, context)


@login_required
@strava_required
def strava_route(request, source_id):
    """
    import form for Strava

    There is a modelform for the route with custom __init__ ans save methods
    to find available checkpoints and save the ones selected by the athlete
    to the route.
    """
    route_form = False

    # create route stub from the athlete and source_id
    route = StravaRoute(
        source_id=source_id,
        athlete=request.user.athlete,
    )

    # with a POST request try to save route and places
    if request.method == "POST":

        # populate checkpoints_formset with POST data
        route_form = post_route_form(request, route)

        # validate forms and save the route and places
        new_route = save_detail_forms(request, route_form)

        # Success! redirect to the page of the newly imported route
        if new_route:
            message = "Route imported successfully from Strava"
            messages.success(request, message)
            return redirect("routes:route", pk=new_route.id)

    if request.method == "GET":

        # fetch route details from Strava API
        try:
            route.get_route_details()

        except ConnectionError as error:
            message = "Could not connect to Strava: {}".format(error)
            messages.error(request, message)

        except AccessUnauthorized:
            message = "Strava Authorization refused. Try to connect to Strava again"
            messages.error(request, message)
            return redirect("strava_connect")

        # populate the route_form with route details
        route, exists = route.refresh_from_db_if_exists()
        route_form = ImportersRouteForm(instance=route)

    context = {
        "route": route,
        "form": route_form,
        "source": STRAVA_SOURCE_INFO,
    }

    template = "importers/route.html"

    return render(request, template, context)


@login_required
@switerland_mobility_required
def switzerland_mobility_routes(request):
    """
    retrieve the athlete's list of routes on Switzerland Mobility Plus
    """

    template = "importers/routes.html"

    # retrieve remote routes list
    try:
        new_routes, old_routes = SwitzerlandMobilityRoute.objects.get_remote_routes_list(
            request.session, request.user.athlete,
        )

    except ConnectionError as error:
        message = "Could not connect to Switzerland Mobility Plus: {}".format(error)
        messages.error(request, message)
        new_routes, old_routes = [], []

    except SwitzerlandMobilityError as error:
        messages.error(request, error)
        new_routes, old_routes = [], []

    context = {
        "source": SWITZERLAND_MOBILITY_SOURCE_INFO,
        "new_routes": new_routes,
        "old_routes": old_routes,
    }

    return render(request, template, context)


@login_required
def switzerland_mobility_route(request, source_id):
    """
    import form for Switzerland Mobility

    There is a modelform for the route with custom __init__ ans save methods
    to find available checkpoints and save the ones selected by the athlete
    to the route.
    """

    # default values for variables passed to the request context
    route_form = False

    # create route stub from the athlete and source_id
    route = SwitzerlandMobilityRoute(
        source_id=source_id,
        athlete=request.user.athlete,
    )

    # with a POST request try to save route and places
    if request.method == "POST":

        # populate the route_form with POST data
        route_form = post_route_form(request, route)

        # validate forms and save the route and places
        new_route = save_detail_forms(request, route_form)

        # Success! redirect to the page of the newly imported route
        if new_route:
            message = "Route imported successfully from Switzerland Mobility"
            messages.success(request, message)
            return redirect("routes:route", pk=new_route.id)

    if request.method == "GET":

        # fetch route details from Switzerland Mobility
        try:
            route.get_route_details()

        except ConnectionError as error:
            messages.error(request, error)

        except SwitzerlandMobilityError as error:
            messages.error(request, error)

        # no exception
        else:
            # populate the route_form with route details
            route, exists = route.refresh_from_db_if_exists()
            route_form = ImportersRouteForm(instance=route)

    context = {
        "route": route,
        "form": route_form,
        "source": SWITZERLAND_MOBILITY_SOURCE_INFO,
    }

    template = "importers/route.html"

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
