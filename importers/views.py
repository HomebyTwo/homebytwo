from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from stravalib.client import Client
from polyline import decode
import json

def index(request):
    client = Client()
    strava_authorize_url = client.authorization_url(
        client_id=settings.STRAVA_CLIENT_ID,
        redirect_uri='http://127.0.0.1:8000/importers/strava/authorized',
    )

    context = {
        'strava_authorize_url': strava_authorize_url,
    }
    return render(request, 'importers/index.html', context)

def strava_authorized(request):
    client = Client()
    code = request.GET.get('code', '')
    access_token = client.exchange_code_for_token(client_id=settings.STRAVA_CLIENT_ID, client_secret=settings.STRAVA_CLIENT_SECRET, code=code)

    client.access_token = access_token
    athlete = client.get_athlete()

    response = "<p>For {id}, I now have an access token {token}</p>".format(id=athlete.id, token=access_token)

    return HttpResponseRedirect('/importers/strava')

def strava_index(request):
    client = Client()
    client.access_token = settings.STRAVA_ACCESS_TOKEN
    athlete = client.get_athlete()
    routes = client.get_routes()

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

