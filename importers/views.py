from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from stravalib.client import Client
import json

from .models import StravaRoute

def index(request):

    # Initialize stravalib client
    client = Client()

    # Generate Strava authorization URL
    strava_authorize_url = client.authorization_url(
        client_id=settings.STRAVA_CLIENT_ID,
        redirect_uri='/importers/strava/authorized',
    )

    context = {
        'strava_authorize_url': strava_authorize_url,
    }
    return render(request, 'importers/index.html', context)

def strava_authorized(request):
    # Initialize stravalib client
    client = Client()

    #Obtain access token
    code = request.GET.get('code', '')
    access_token = client.exchange_code_for_token(
                        client_id=settings.STRAVA_CLIENT_ID,
                        client_secret=settings.STRAVA_CLIENT_SECRET,
                        code=code,
                    )

    client.access_token = access_token

    return HttpResponseRedirect('/importers/strava')

def strava_index(request):
    # Check if we have a Strava access token
    access_token = settings.STRAVA_ACCESS_TOKEN

    if not access_token:
        #render the Strava connect button
        return render(request, 'importers/strava/connect.html')

    else:
        client = Client()
        client.access_token = access_token

    athlete = client.get_athlete()

    # Retrieve routes from DB
    routes = StravaRoute.objects.all()

    if not routes:
        routes = StravaRoute.objects.get_routes_list_from_server()


    context = {
        'athlete': athlete,
        'routes': routes,
    }
    return render(request, 'importers/strava/index.html', context)

def strava_detail(request, strava_route_id):
    client = Client()
    client.access_token = settings.STRAVA_ACCESS_TOKEN
    route = client.get_route(strava_route_id)
    route.geom = json.dumps(decode(route.map.polyline))

    context = {
        'route': route,
    }
    return render(request, 'importers/strava/detail.html', context)

def switzerland_mobility_index(request):
    routes = SwitzerlandMobilityRoute.objects.order_by('-created')
    context = {
        'routes': routes,
    }
    return render(request, 'routes/index.html', context)

