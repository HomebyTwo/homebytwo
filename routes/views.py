from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.gis.measure import D, Distance
from django.contrib.gis.db.models.functions import Length

from .models import Route

# Create your views here.
def index(request):
    routes = Route.objects.annotate(distance=Length('geom')).order_by('-created')
    context = {
        'routes': routes,
    }
    return render(request, 'routes/index.html', context)

def detail(request, route_id):
    route = Route.objects.get(id=route_id)
    context = {
        'route': route,
    }
    return render(request, 'routes/detail.html', context)

def edit(request, route_id):
    response = "You are looking at the edit page of route %s"
    return HttpResponse(response % route_id)