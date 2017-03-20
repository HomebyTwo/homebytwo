from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.generic.edit import UpdateView

from .models import Route, RoutePlace
from .forms import RouteImageForm


def routes(request):
    routes = Route.objects.order_by('name')
    context = {
        'routes': routes,
    }
    return render(request, 'routes/routes.html', context)


def route(request, pk):
    route = Route.objects.get(id=pk)
    places = RoutePlace.objects.filter(route=pk)
    for place in places:
        place.schedule = route.get_time_data_from_line_location(
                    place.line_location,
                    'schedule'
        )

    context = {
        'route': route,
        'places': places
    }
    return render(request, 'routes/route.html', context)


@method_decorator(login_required, name='dispatch')
class ImageFormView(UpdateView):
    """
    Playing around with class based views.
    """
    model = Route
    form_class = RouteImageForm
    template_name_suffix = '_image_form'


@login_required
def edit(request, route_id):
    response = "You are looking at the edit page of route %s"
    return HttpResponse(response % route_id)
