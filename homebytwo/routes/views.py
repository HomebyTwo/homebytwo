import json
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.gis.measure import D
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.edit import DeleteView, UpdateView
from django.views.generic.list import ListView

from pytz import utc

from .models import Activity, Route, RoutePlace, WebhookTransaction
from .tasks import import_athlete_strava_activities


@login_required
def routes(request):
    routes = Route.objects.order_by("name")
    routes = routes.filter(athlete=request.user.athlete)
    context = {
        "routes": routes,
    }

    return render(request, "routes/routes.html", context)


def route(request, pk):
    # load route from Database
    route = get_object_or_404(Route, id=pk)

    # calculate the schedule based on user data
    route.calculate_projected_time_schedule(request.user)

    # retrieve checkpoints along the way and enrich them with data
    places = RoutePlace.objects.filter(route=pk)
    places = places.select_related("route", "place")

    for place in places:
        place.schedule = route.get_time_data(place.line_location, "schedule")
        place.altitude = place.get_altitude()
        place.distance = D(m=place.line_location * route.length)

    # enrich start and end place with data
    if route.start_place_id:
        route.start_place.schedule = route.get_time_data(0, "schedule")
        route.start_place.altitude = route.get_distance_data(0, "altitude")
    if route.end_place_id:
        route.end_place.schedule = route.get_time_data(1, "schedule")
        route.end_place.altitude = route.get_distance_data(1, "altitude")

    context = {"route": route, "places": places}
    return render(request, "routes/route.html", context)


@login_required
def import_strava_activities(request):
    if request.method == "GET":
        import_athlete_strava_activities.delay(request.user.athlete.id)
        messages.success(request, "We are importing your Strava activities!")
        return redirect("routes:activities")


@csrf_exempt
def strava_webhook(request):
    """
    handle events sent by the Strava Webhook Events API

    Strava validates a subscription with a GET request to the callback URL.
    Events from the subscriptions are POSTed to the callback URL.
    Documentation available at https://developers.strava.com/docs/webhooks/
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

        return HttpResponse(status=200)

    # Anything else
    return HttpResponse("Unauthorized", status=401)


@method_decorator(login_required, name="dispatch")
class ImageFormView(UpdateView):
    """
    Playing around with class based views.
    """

    model = Route
    fields = ["image"]
    template_name_suffix = "_image_form"


@method_decorator(login_required, name="dispatch")
class RouteDelete(DeleteView):
    """
    Playing around with class based views.
    """

    model = Route
    success_url = reverse_lazy("routes:routes")


@method_decorator(login_required, name="dispatch")
class RouteEdit(UpdateView):
    model = Route
    fields = ["activity_type", "name", "description", "image"]

    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # if the activity_type has changed recalculate the route schedule
        if "activity_type" in form.changed_data:
            form.instance.calculate_projected_time_schedule(self.request.user)

        return super(RouteEdit, self).form_valid(form)


@method_decorator(login_required, name="dispatch")
class ActivityList(ListView):
    paginate_by = 50
    context_object_name = "strava_activities"

    def get_queryset(self):
        return Activity.objects.filter(athlete=self.request.user.athlete)
