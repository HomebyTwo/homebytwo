from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch
from django.views.decorators.http import require_POST

from ..routes.forms import RouteForm
from .decorators import remote_connection
from .forms import GpxUploadForm, SwitzerlandMobilityLogin
from .utils import get_proxy_class_from_data_source, save_detail_forms, split_routes
from ..routes.tasks import update_route_elevation_data_task


@login_required
def index(request):
    return render(request, "importers/index.html")


@login_required
@remote_connection
def import_routes(request, data_source):
    """
    retrieve the athlete's list of routes on Strava
    """

    template = "importers/routes.html"

    # retrieve proxy class from data source in url
    route_class = get_proxy_class_from_data_source(data_source)

    # retrieve remote routes list
    remote_routes = route_class.objects.get_remote_routes_list(
        athlete=request.user.athlete,
        cookies=request.session.get("switzerland_mobility_cookies"),
    )

    # retrieve the athlete's list of routes already saved in homebytwo
    local_routes = route_class.objects.for_user(request.user)

    # split routes in 3 lists
    new_routes, existing_routes, deleted_routes = split_routes(
        remote_routes, local_routes
    )

    context = {
        "new_routes": new_routes,
        "existing_routes": existing_routes,
        "deleted_routes": deleted_routes,
        "data_source_name": route_class.DATA_SOURCE_NAME,
        "data_source_link": route_class.DATA_SOURCE_LINK,
    }

    return render(request, template, context)


@login_required
@remote_connection
def import_route(request, data_source, source_id):
    """
    import routes from external sources

    There is a modelform for the route with custom __init__ and save methods
    to find available checkpoints and save the ones selected by the athlete
    to the route.
    """

    template = "routes/route/route_form.html"

    # create stub or retrieve from db
    route_class = get_proxy_class_from_data_source(data_source)
    route, update = route_class.get_or_stub(source_id, request.user.athlete)

    # fetch route details from Remote API
    route.get_route_details(request.session.get("switzerland_mobility_cookies"))
    route.update_track_details_from_data()

    if request.method == "POST":
        # instantiate form with POST data
        route_form = RouteForm(update=update, data=request.POST, instance=route)

        # validate forms and save the route and places
        new_route = save_detail_forms(request, route_form)

        # Success! redirect to the page of the newly imported route
        if new_route:
            # get better elevation data than the one from Strava
            if new_route.data_source == "strava":
                update_route_elevation_data_task.delay(new_route.pk)

            message_action = "updated" if update else "imported"
            message = "Route {} successfully from {}"
            messages.success(
                request, message.format(message_action, route.DATA_SOURCE_NAME)
            )
            return redirect("routes:route", pk=new_route.pk)

    if request.method == "GET":
        # populate the route_form with route details
        route_form = RouteForm(update=update, instance=route)

    context = {
        "object": route,
        "form": route_form,
    }

    return render(request, template, context)


@login_required
@require_POST
def upload_gpx(request):
    """
    Create a new route from GPX information, save it, and redirect to the import route.
    """
    form = GpxUploadForm(request.POST, files=request.FILES)

    if form.is_valid():
        route = form.save(commit=False)
        route.athlete = request.user.athlete
        route.save()
        return redirect("routes:edit", pk=route.pk)

    template = "importers/index.html"
    return render(request, template, {"gpx_upload_form": form})


@login_required
@remote_connection
def switzerland_mobility_login(request):

    template = "importers/switzerland_mobility/login.html"

    # POST request, validate and login
    if request.method == "POST":

        # instantiate login form and populate it with POST data:
        form = SwitzerlandMobilityLogin(request.POST)

        # If the form validates,
        # try to retrieve the Switzerland Mobility cookies
        if form.is_valid():
            cookies = form.retrieve_authorization_cookie(request)

            # cookies retrieved successfully
            if cookies:
                # add cookies to the user session
                request.session["switzerland_mobility_cookies"] = cookies

                # check if we can redirect to a route after login
                route_id = request.POST.get("route_id", request.GET.get("route_id", ""))
                if route_id:
                    try:
                        return redirect(
                            "import_route",
                            data_source="switzerland_mobility",
                            source_id=route_id,
                        )

                    # someone messed up the query string
                    except NoReverseMatch:
                        pass

                return redirect("import_routes", data_source="switzerland_mobility")

        # something went wrong, render the login page,
        context = {"form": form}
        return render(request, template, context)

    # print the form
    elif request.method == "GET":
        context = {"form": SwitzerlandMobilityLogin()}
        return render(request, template, context)

    else:
        return HttpResponse("Method not allowed", status=405)
