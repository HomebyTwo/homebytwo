from django.shortcuts import render
from django.http import HttpResponse

from .models import Route

# Create your views here.
def index(request):
    routes = Route.objects.order_by('-created')
    context = {
        'routes': routes,
    }
    return render(request, 'routes/index.html', context)

def detail(request, route_id):
    return HttpResponse("You're looking at route %s." % route_id)

def edit(request, route_id):
    response = "You are looking at the edit page of route %s"
    return HttpResponse(response % route_id)