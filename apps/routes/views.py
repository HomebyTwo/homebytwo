from django.shortcuts import render
from django.http import HttpResponse

from django.contrib.auth.decorators import login_required

from .models import Route, RoutePlace


def index(request):
    routes = Route.objects.order_by('name')
    context = {
        'routes': routes,
    }
    return render(request, 'routes/index.html', context)


def detail(request, route_id):
    route = Route.objects.get(id=route_id)
    places = RoutePlace.objects.filter(route=route_id)
    context = {
        'route': route,
        'places': places
    }
    return render(request, 'routes/detail.html', context)


@login_required
def edit(request, route_id):
    response = "You are looking at the edit page of route %s"
    return HttpResponse(response % route_id)


@login_required
def importers(request):
    return render(request, 'routes/importers.html')