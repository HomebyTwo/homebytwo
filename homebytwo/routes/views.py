import json
from datetime import datetime
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import BooleanField, Case, F, Value, When
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
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
from .forms import ActivityPerformanceForm, RouteForm
from .models import Activity, ActivityType, Route, WebhookTransaction
from .tasks import (
    import_strava_activities_task,
    import_strava_activity_streams_task,
    process_strava_events,
    train_prediction_models_task,
    upload_route_to_garmin_task,
)


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
            gear_id = performance_form.cleaned_data.get("gear")
            route.activity_type, created = ActivityType.objects.get_or_create(
                name=activity_type_name
            )

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

        gear_id = (
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

    # calculate route schedule for display
    route.calculate_projected_time_schedule(
        user=request.user,
        gear=gear_id,
        workout_type=workout_type,
    )

    # retrieve checkpoints along the way
    checkpoints = route.checkpoint_set.all()
    checkpoints = checkpoints.select_related("route", "place")

    # schedule is not a calculated property on Checkpoint: the schedule can change
    for checkpoint in checkpoints:
        checkpoint.schedule = route.get_time_data(checkpoint.line_location, "schedule")

    context = {
        "route": route,
        "checkpoints": checkpoints,
        "form": performance_form,
    }
    return render(request, "routes/route/route.html", context)


@method_decorator(login_required, name="dispatch")
class RouteEdit(PermissionRequiredMixin, UpdateView):
    """
    edit route name, activity_type and checkpoints.
    """

    model = Route
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
    permission_required = "routes.delete_route"
    success_url = reverse_lazy("routes:routes")
    template_name = "routes/route/route_confirm_delete.html"


@require_safe
def route_checkpoints_list(request, pk):
    route = get_object_or_404(Route, pk=pk, athlete=request.user.athlete)

    possible_checkpoints = route.find_possible_checkpoints()
    existing_checkpoints = route.checkpoint_set.all()

    checkpoints_dicts = [
        {
            "name": checkpoint.place.name,
            "field_value": checkpoint.field_value,
            "geom": json.loads(checkpoint.place.get_geojson(fields=["name"])),
            "place_type": checkpoint.place.place_type.name,
            "checked": checkpoint in existing_checkpoints,
        }
        for checkpoint in possible_checkpoints
    ]

    return JsonResponse({"checkpoints": checkpoints_dicts})


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

    def post(self, request):
        self.object_list = self.get_queryset()
        context_data = self.get_context_data()
        page_activity_ids = context_data[
            self.get_context_object_name(self.object_list)
        ].values_list("pk", flat=True)

        use_for_training_ids = request.POST.getlist("use_for_training")
        Activity.objects.for_user(self.request.user).filter(
            pk__in=page_activity_ids
        ).annotate(
            new_use_for_training=Case(
                When(id__in=use_for_training_ids, then=True),
                default=Value(False),
                output_field=BooleanField(),
            )
        ).update(
            use_for_training=F("new_use_for_training")
        )

        train_prediction_models_task.delay(request.user.athlete.id)

        activities_url = reverse("routes:activities")
        page_number = context_data["page_obj"].number

        redirect_url = (
            activities_url
            if page_number == 1
            else activities_url + f"?page={page_number}"
        )

        return redirect(redirect_url)


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
