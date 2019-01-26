import json

from .models import Route, Checkpoint
from django.contrib.auth.decorators import login_required
from django.contrib.gis.measure import D
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic.edit import UpdateView, DeleteView


@login_required
def routes(request):
    routes = Route.objects.order_by('name')
    routes = routes.filter(owner=request.user)
    context = {
        'routes': routes,
    }

    return render(request, 'routes/routes.html', context)


def route(request, pk):
    # load route from Database
    route = get_object_or_404(Route, id=pk)

    # calculate the schedule based on user data
    route.calculate_projected_time_schedule(request.user)

    # retrieve checkpoints along the way and enrich them with data
    checkpoints = Checkpoint.objects.filter(route=pk)
    checkpoints = checkpoints.select_related('route', 'place')

    for checkpoint in checkpoints:
        checkpoint.schedule = route.get_time_data(checkpoint.line_location, 'schedule')

    # enrich start and end place with data
    if route.start_place_id:
        route.start_place.schedule = route.get_time_data(0, 'schedule')
        route.start_place.altitude = route.get_distance_data(0, 'altitude')
    if route.end_place_id:
        route.end_place.schedule = route.get_time_data(1, 'schedule')
        route.end_place.altitude = route.get_distance_data(1, 'altitude')

    context = {
        'route': route,
        'checkpoints': checkpoints
    }
    return render(request, 'routes/route.html', context)


@method_decorator(login_required, name='dispatch')
class ImageFormView(UpdateView):
    """
    Playing around with class based views.
    """
    model = Route
    fields = ['image']
    template_name_suffix = '_image_form'


@method_decorator(login_required, name='dispatch')
class RouteDelete(DeleteView):
    """
    Playing around with class based views.
    """
    model = Route
    success_url = reverse_lazy('routes:routes')


@method_decorator(login_required, name='dispatch')
class RouteEdit(UpdateView):
    model = Route
    fields = ['activity_type', 'name', 'description', 'image']

    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # if the activity_type has changed recalculate the route schedule
        if 'activity_type' in form.changed_data:
            form.instance.calculate_projected_time_schedule(self.request.user)

        return super(RouteEdit, self).form_valid(form)


def route_checkpoints_list(request, pk):
    route = get_object_or_404(Route, pk=pk, owner=request.user)

    checkpoints = route.find_checkpoints()
    checkpoints_dicts = [
        {
            'name': checkpoint.place.name,
            'line_location': checkpoint.line_location,
            'geom': json.loads(checkpoint.place.geom.json)
        }
        for checkpoint in checkpoints
    ]

    return JsonResponse({'checkpoints': checkpoints_dicts})
