from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse

from .models import Route


def index(request):
    routes = Route.objects.order_by('name')
    context = {
        'routes': routes,
    }
    return render(request, 'routes/index.html', context)


def detail(request, slug):
    route = get_object_or_404(Route, slug=slug)
    context = {
        'route': route,
    }
    return render(request, 'routes/detail.html', context)


def by_id(request, route_id):
    route = Route.objects.get(id=route_id)
    context = {
        'route': route,
    }
    return render(request, 'routes/detail.html', context)


def edit(request, route_id):
    response = "You are looking at the edit page of route %s"
    return HttpResponse(response % route_id)
