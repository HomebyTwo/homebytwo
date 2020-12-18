import json
from datetime import datetime
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    HttpResponseForbidden,
    JsonResponse,
)
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.http import urlencode
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_safe
from django.views.generic.edit import DeleteView, UpdateView
from django.views.generic.list import ListView

from pytz import utc
from rules.contrib.views import (
    PermissionRequiredMixin,
    objectgetter,
    permission_required,
)

from ..importers.decorators import remote_connection, strava_required
from ..importers.exceptions import SwitzerlandMobilityError
from .forms import ActivityPerformanceForm, CheckpointsForm, RouteForm, StartPlaceForm, EndPlaceForm
from .models import Activity, ActivityType, Route, WebhookTransaction
from .tasks import (
    import_strava_activities_task,
    import_strava_activity_streams_task,
    process_strava_events,
    train_prediction_models_task,
    upload_route_to_garmin_task,
)
from .utils import save_form_checkpoints


@login_required
@require_safe
def view_routes(request):
    routes = Route.objects.for_user(request.user)
    routes = routes.order_by("name")
    context = {"routes": routes}

    return render(request, "routes/routes.html", context)


@permission_required("routes.view_route", fn=objectgetter(Route))
def view_route(request, pk):
    """
    display route schedule based on the prediction model of the logged-in athlete

    The route page contains a simple form to change the route activity_type
    and tweak the schedule.

    If the athlete is not logged in or if the logged-in athlete has no
    prediction model for the selected activity type, a default prediction model
    is used.

    """
    route = get_object_or_404(Route, pk=pk)

    if request.method == "POST":
        performance_form = ActivityPerformanceForm(
            route,
            request.user.athlete if request.user.is_authenticated else None,
            data=request.POST,
        )

        if performance_form.is_valid():
            activity_type_name = performance_form.cleaned_data["activity_type"]
            workout_type = performance_form.cleaned_data.get("workout_type")
            gear = performance_form.cleaned_data.get("gear")

            # update route instance activity type
            route.activity_type = ActivityType.objects.get(name=activity_type_name)

    # invalid form: the activity type was changed in the form,
    # we reinitialize the form to get gear and workout type
    # matching the new activity type
    if request.method == "GET" or not performance_form.is_valid():
        # get unbound performance form with initial values
        performance_form = ActivityPerformanceForm(
            route,
            request.user.athlete if request.user.is_authenticated else None,
            initial={"activity_type": route.activity_type.name},
        )

        gear = (
            performance_form.fields["gear"].choices[0][0]
            if "gear" in performance_form.fields
            else None
        )

        workout_type = (
            performance_form.fields["workout_type"].choices[0][0]
            if "workout_type" in performance_form.fields
            else None
        )

    # restore route data from remote source if data file was corrupted or deleted
    if route.data is None:
        try:
            route.geom, route.data = route.get_route_data(
                cookies=request.session.get("switzerland_mobility_cookies")
            )
        except SwitzerlandMobilityError:
            raise Http404("Route information could not be found.")

        else:
            route.update_permanent_track_data(min_step_distance=1, max_gradient=100)
            route.update_track_details_from_data()

    # prepare GET parameters for endpoint urls passed to the Checkpoints Elm module
    perf_params = {"activity_type": route.activity_type}
    if gear is not None:
        perf_params["gear"] = gear
    if workout_type is not None:
        perf_params["workout_type"] = workout_type
    encoded_perf_params = urlencode(perf_params)

    # create the context dict for the Checkpoints Elm app
    context = {
        "route": route,
        "form": performance_form,
        "checkpoints_config": {
            "displayUrl": route.schedule_url + "?" + encoded_perf_params,
            "editUrl": route.edit_schedule_url + "?" + encoded_perf_params,
            "canEdit": request.user.has_perm("routes.change_route", route),
            "csrfToken": get_token(request),
        },
    }
    return render(request, "routes/route/route.html", context)


@method_decorator(login_required, name="dispatch")
class RouteEdit(PermissionRequiredMixin, UpdateView):
    """
    edit route name, activity_type and checkpoints.
    """

    model = Route
    context_object_name = "route"
    permission_required = "routes.change_route"
    form_class = RouteForm
    template_name = "routes/route/route_form.html"


@method_decorator(login_required, name="dispatch")
@method_decorator(remote_connection, name="dispatch")
class RouteUpdate(RouteEdit):
    """
    re-import route data from remote data-source keeping selected checkpoints by name.
    """

    def get_permission_object(self):
        """
        do not hit the remote server to check permissions
        """
        pk = self.kwargs.get(self.pk_url_kwarg)
        return get_object_or_404(Route, pk=pk)

    def get_object(self, queryset=None):
        """
        routes that do not have a data_source raise NotImplementedErrors
        and trigger a 404.
        """
        pk = self.kwargs.get(self.pk_url_kwarg)
        if pk is not None:
            route = get_object_or_404(Route, pk=pk)

            try:
                return route.update_from_remote(
                    self.request.session.get("switzerland_mobility_cookies", None)
                )
            except NotImplementedError:
                raise Http404

    def get_form_kwargs(self):
        """Return the keyword arguments for instantiating the form."""
        kwargs = super().get_form_kwargs()
        kwargs.update({"update": True})
        return kwargs


@method_decorator(login_required, name="dispatch")
class RouteDelete(PermissionRequiredMixin, DeleteView):
    """
    Class based views are not so bad after all.
    """

    model = Route
    context_object_name = "route"
    permission_required = "routes.delete_route"
    success_url = reverse_lazy("routes:routes")
    template_name = "routes/route/route_confirm_delete.html"


def route_schedule(request, pk):
    """
    retrieve JSON array of Checkpoint objects for a route

    if edit is requested, retrieve all possible checkpoints for the route,
    otherwise return only the checkpoints currently attached to the route.
    When new checkpoints are posted, begin in "edit" mode, and switch
    to "display" once the posted data is validated and saved.
    """

    # retrieve route
    route = get_object_or_404(Route, pk=pk)

    # check permission to edit and display checkpoints
    if not request.user.has_perm("routes.view_route", route):
        raise HttpResponseForbidden()

    # validate GET parameters for schedule calculation
    athlete = request.user.athlete if request.user.is_authenticated else None
    perf_form = ActivityPerformanceForm(route, athlete, data=request.GET)

    if perf_form.is_valid():
        activity_type = perf_form.cleaned_data.get("activity_type")
        workout_type = perf_form.cleaned_data.get("workout_type")
        gear = perf_form.cleaned_data.get("gear")
    else:
        activity_type = workout_type = gear = None

    # calculate time schedule
    route.calculate_projected_time_schedule(
        request.user, activity_type, workout_type, gear
    )

    # retrieve existing checkpoints
    existing_checkpoints = route.checkpoints.all()

    # save posted checkpoints
    if request.method == "POST":

        # validate submitted checkpoints, also check permissions
        post_data = json.loads(request.body)
        checkpoints_form = CheckpointsForm(data=post_data)

        if checkpoints_form.is_valid():
            existing_checkpoints = save_form_checkpoints(
                route,
                existing_checkpoints,
                checkpoints_data=checkpoints_form.cleaned_data["checkpoints"],
            )

            # switch to returning "display" checkpoints if everything flies
            edit = False
    # check if edit was requested and user has permission
    if edit:
        checkpoints = route.find_possible_checkpoints()
    else:
        checkpoints = existing_checkpoints

    # prepare checkpoint dicts for the JSON response
    checkpoint_dicts = [
        checkpoint.get_json(existing_checkpoints) for checkpoint in checkpoints
    ]

    return JsonResponse(
        {
            "checkpoints": checkpoint_dicts,
            "start": route.get_start_place_json(),
            "finish": route.get_end_place_json(),
        }
    )


def route_checkpoints_edit(request, pk):

    # retrieve route
    route = get_object_or_404(Route, pk=pk)

    if not request.user.has_perm("routes.change_route", route):
        raise HttpResponseForbidden()

    # validate GET parameters for schedule calculation
    athlete = request.user.athlete if request.user.is_authenticated else None
    perf_form = ActivityPerformanceForm(route, athlete, data=request.GET)

    if perf_form.is_valid():
        activity_type = perf_form.cleaned_data.get("activity_type")
        workout_type = perf_form.cleaned_data.get("workout_type")
        gear = perf_form.cleaned_data.get("gear")
    else:
        activity_type = workout_type = gear = None

    # calculate time schedule
    route.calculate_projected_time_schedule(
        request.user, activity_type, workout_type, gear
    )

    # retrieve existing checkpoints
    existing_checkpoints = route.checkpoints.all()

    shouldFetchAllCheckpoints = True

    # save posted checkpoints
    if request.method == "POST":

        # validate submitted checkpoints, also check permissions
        post_data = json.loads(request.body)
        checkpoints_form = CheckpointsForm(data=post_data)

        if checkpoints_form.is_valid():
            existing_checkpoints = save_form_checkpoints(
                route,
                existing_checkpoints,
                checkpoints_data=checkpoints_form.cleaned_data["checkpoints"],
            )

            # switch to returning "display" checkpoints if everything flies
            shouldFetchAllCheckpoints = False

    # check if edit was requested and user has permission
    if shouldFetchAllCheckpoints:
        checkpoints = route.find_possible_checkpoints()
    else:
        checkpoints = existing_checkpoints

    # prepare checkpoint dicts for the JSON response
    checkpoint_dicts = [
        checkpoint.get_json(existing_checkpoints) for checkpoint in checkpoints
    ]

    return JsonResponse({ "checkpoints": checkpoint_dicts })


def route_start_edit(request, pk):
    route = get_object_or_404(Route, pk=pk)

    if not request.user.has_perm("routes.change_route", route):
        raise HttpResponseForbidden()

    if request.method == "POST":

        # validate submitted checkpoints, also check permissions
        post_data = json.loads(request.body)
        place_start_form = StartPlaceForm(data=post_data)

        if place_start_form.is_valid():
            route.place_start = place_start_form.cleaned_data.start
            route.save(update_fields=['place_start'])

    return JsonResponse({ "start": route.get_start_place_json() })


def route_finish_edit(request, pk):
    route = get_object_or_404(Route, pk=pk)

    if not request.user.has_perm("routes.change_route", route):
        raise HttpResponseForbidden()

    if request.method == "POST":
        # validate submitted checkpoints, also check permissions
        post_data = json.loads(request.body)
        place_end_form = EndPlaceForm(data=post_data)

        if place_end_form.is_valid():
            route.end_place = place_end_form.cleaned_data.end
            route.save(update_fields=['end_place'])

    return JsonResponse({ "finish": route.get_end_place_json() })


@login_required
@permission_required(
    "routes.download_route", fn=objectgetter(Route), raise_exception=True
)
def download_route_gpx(request, pk):
    route = get_object_or_404(Route, pk=pk)

    route.calculate_projected_time_schedule(request.user)

    return FileResponse(
        BytesIO(bytes(route.get_gpx(), encoding="utf-8")),
        as_attachment=True,
        filename=route.gpx_filename,
        content_type="application/gpx+xml; charset=utf-8",
    )


@login_required
@permission_required(
    "routes.garmin_upload_route", fn=objectgetter(Route), raise_exception=True
)
def upload_route_to_garmin(request, pk):
    route = get_object_or_404(Route, pk=pk)

    # set garmin_id to 1 == upload requested
    route.garmin_id = 1
    route.save(update_fields=["garmin_id"])

    # upload route to Garmin with a Celery task
    upload_route_to_garmin_task.delay(route.id, route.athlete.id)
    message = "Your route is uploading to Garmin. Check back soon to access it."
    messages.success(request, message)

    return redirect(route)


@method_decorator(login_required, name="dispatch")
@method_decorator(require_safe, name="dispatch")
class ActivityList(ListView):
    paginate_by = 50
    context_object_name = "strava_activities"

    def get_queryset(self):
        return Activity.objects.for_user(self.request.user)


@login_required
@strava_required  # only the superuser can be logged-in without a Strava account
def import_strava_activities(request):
    """
    send a task to import the athlete's Strava activities and redirect
    to the activity list. TODO: use websockets to monitor progress
    """
    import_strava_activities_task.delay(request.user.athlete.id)
    messages.success(request, "We are importing your Strava activities!")
    return redirect("routes:activities")


@login_required
@strava_required  # only the superuser can be logged-in without a Strava account
def import_strava_streams(request):
    """
    trigger a task to import streams for activities without streams.
    """
    activities = request.user.athlete.activities
    activities = activities.filter(streams__isnull=True)
    activities = activities.order_by("-start_date")

    for activity in activities:
        import_strava_activity_streams_task.delay(activity.strava_id)
    messages.success(request, "We are importing your Strava streams!")
    return redirect("routes:activities")


@login_required
def train_prediction_models(request):
    """
    trigger a task to calculate prediction models
    for all activity types found in the athlete's activities.
    """
    train_prediction_models_task.delay(request.user.athlete.id)

    messages.success(request, "We are calculating your prediction models!")
    return redirect("routes:activities")


@csrf_exempt
def strava_webhook(request):
    """
    handle events sent by the Strava Webhook Events API, the API to receive
    Strava updates instead of polling.

    Strava validates a subscription with a GET request to the callback URL.
    Events from the subscriptions are POSTed to the callback URL. For now
    Strava has no verification mechanism for the POST requests.
    Documentation is available at https://developers.strava.com/docs/webhooks/
    """

    # subscription validation
    if request.method == "GET":

        # validate the request and return the hub.challenge as json
        if request.GET.get("hub.verify_token") == settings.STRAVA_VERIFY_TOKEN:
            hub_challenge_json = {"hub.challenge": request.GET.get("hub.challenge")}
            return JsonResponse(hub_challenge_json)

    # event submission
    elif request.method == "POST":

        # decode json object
        body = request.body.decode("utf-8")
        data = json.loads(body)

        # keep only metadata with string values in the transaction object
        meta_data = {k: v for k, v in request.META.items() if isinstance(v, str)}

        # save transaction object to the database
        WebhookTransaction.objects.create(
            body=data,
            request_meta=meta_data,
            date_generated=datetime.fromtimestamp(data["event_time"], tz=utc),
        )

        # import activity into the database
        process_strava_events.delay()

        return HttpResponse(status=200)

    # Anything else
    return HttpResponse("Unauthorized", status=401)
