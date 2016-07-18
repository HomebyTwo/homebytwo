from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponseRedirect
from stravalib.client import Client as StravaClient

from .models import StravaRoute, SwitzerlandMobilityRoute
from routes.models import Athlete
from django.contrib.auth.decorators import login_required


@login_required
def index(request):
    context = {
        'nothing': 'Nothing',
    }
    return render(request, 'importers/index.html', context)


@login_required
def strava_connect(request):
    # Initialize stravalib client
    strava_client = StravaClient()

    # Get user from request
    redirect = request.build_absolute_uri('/importers/strava/authorized/')
    # Generate Strava authorization URL
    strava_authorize_url = strava_client.authorization_url(
        client_id=settings.STRAVA_CLIENT_ID,
        redirect_uri=redirect,
    )

    context = {
        'strava_authorize_url': strava_authorize_url,
    }
    # Render the Strava connect button
    return render(request, 'importers/strava/connect.html', context)


@login_required
def strava_authorized(request):
    # Initialize stravalib client
    strava_client = StravaClient()

    # Obtain access token
    code = request.GET.get('code', '')
    access_token = strava_client.exchange_code_for_token(
                        client_id=settings.STRAVA_CLIENT_ID,
                        client_secret=settings.STRAVA_CLIENT_SECRET,
                        code=code,
                    )

    # Save access token to athlete
    user = request.user
    user.athlete.strava_token = access_token
    user.athlete.save()

    return HttpResponseRedirect('/importers/strava')


@login_required
def strava_index(request):
    # Get user from request
    user = request.user

    # Initialize stravalib client
    strava_client = StravaClient()

    athlete, created = Athlete.objects.get_or_create(user=user)

    # No token, athlete has never connected
    if not athlete.strava_token:
        return HttpResponseRedirect('/importers/strava/connect')

    else:
        strava_client.access_token = athlete.strava_token

    try:
        athlete = strava_client.get_athlete()

    except Exception as e:
        # Bad Token: Destroy bad token and render Strava connect button button
        print e
        athlete.strava_token = ''
        athlete.save()
        return HttpResponseRedirect('/importers/strava/connect')

    except Exception as e:
        print e
        """Cannot connect to Strava API:
        Destroy bad token and render Strava connect button button"""
        return HttpResponseRedirect('/importers/strava/unavailable')

    # Retrieve routes from DB
    try:
        routes = StravaRoute.objects.filter(user=user)

    except Exception as e:
        print e

    if not routes:
        StravaRoute.objects.get_routes_list_from_server(user)

    routes = StravaRoute.objects.filter(user=user)

    context = {
        'athlete': athlete,
        'routes': routes,
    }
    return render(request, 'importers/strava/index.html', context)


def switzerland_mobility_index(request):
    routes = SwitzerlandMobilityRoute.objects.order_by('-created')
    context = {
        'routes': routes,
    }
    return render(request, 'routes/index.html', context)
