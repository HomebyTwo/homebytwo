from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from stravalib.client import Client as StravaClient

from .models import StravaRoute, SwitzerlandMobilityRoute
from routes.models import Athlete
from django.contrib.auth.decorators import login_required

from .forms import SwitzerlandMobilityLogin, SwitzerlandMobilityRouteForm


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
        print(e)
        athlete.strava_token = ''
        athlete.save()
        return HttpResponseRedirect('/importers/strava/connect')

    except Exception as e:
        print(e)
        """Cannot connect to Strava API:
        Destroy bad token and render Strava connect button button"""
        return HttpResponseRedirect('/importers/strava/unavailable')

    # Retrieve routes from DB
    try:
        routes = StravaRoute.objects.filter(user=user)

    except Exception as e:
        print(e)

    if not routes:
        StravaRoute.objects.get_routes_list_from_server(user)

    routes = StravaRoute.objects.filter(user=user)

    context = {
        'athlete': athlete,
        'routes': routes,
    }
    return render(request, 'importers/strava/index.html', context)


@login_required
def switzerland_mobility_index(request):
    # Check if logged-in to Switzeland Mobility
    try:
        request.session['switzerland_mobility_cookies']

    # No login cookies
    except KeyError:
        # redirect to the switzeland mobility login page
        redirect_url = reverse('switzerland_mobility_login')
        return HttpResponseRedirect(redirect_url)

    # Retrieve remote routes from Switzerland Mobility
    manager = SwitzerlandMobilityRoute.objects
    new_routes, old_routes, response = manager.get_remote_routes(
        request.session, request.user)

    template = 'importers/switzerland_mobility/index.html'
    context = {
        'new_routes': new_routes,
        'old_routes': old_routes,
        'response': response
    }

    return render(request, template, context)


@login_required
def switzerland_mobility_detail(request, source_id):
    template = 'importers/switzerland_mobility/detail.html'
    route_id = int(source_id)

    # if it is a POST request try to import the route
    if request.method == 'POST':
        form = SwitzerlandMobilityRouteForm(request.POST)

        try:
            new_route = form.save(commit=False)
            new_route.user = request.user
            new_route.save()

            # redirect to the imported route page
            redirect_url = reverse('routes:detail', args=(new_route.id,))
            return HttpResponseRedirect(redirect_url)

        # validation errors, print the message
        except ValueError:
            route = False
            response = {
                'error': True,
                'message': str(form.errors),
            }

    # GET request
    else:
        # fetch route details from Switzerland Mobility
        route, response = SwitzerlandMobilityRoute.objects.get_remote_route(route_id)

        # route details succesfully retrieved
        if route:
            form = SwitzerlandMobilityRouteForm(instance=route)
            route.user = request.user

        # route details could not be retrieved
        else:
            form = False

    context = {
        'route': route,
        'response': response,
        'form': form
    }

    return render(request, template, context)


@login_required
def switzerland_mobility_login(request):
    template = 'importers/switzerland_mobility/login.html'

    # POST request, validate and login
    if request.method == 'POST':

        # instanciate login form and populate it with POST data:
        form = SwitzerlandMobilityLogin(request.POST)

        # If the form validates,
        # try to retrieve the Switzerland Mobility cookies
        if form.is_valid():
                cookies, response = form.retrieve_authorization_cookie()

                # cookies retrieved successfully
                if not response['error']:
                    # add cookies to the user session
                    request.session['switzerland_mobility_cookies'] = cookies
                    # redirect to the route list
                    redirect_url = reverse('switzerland_mobility_index')
                    return HttpResponseRedirect(redirect_url)
                # something went wrong, render the login page with the error
                else:
                    context = {
                        'form': form,
                        'error': response['error'],
                        'message': response['message'],
                    }
                    return render(request, template, context)

        # form validation error, render the page with the errors
        else:
            error = True
            message = 'An error has occured. '

            for error in form.errors:
                message += error + ': '
                for error_message in form.errors[error]:
                    message += error_message
            context = {
                'form': form,
                'error': response['error'],
                'message': response['message'],
            }
            return render(request, template, context)

    # GET request, print the form
    else:
        form = SwitzerlandMobilityLogin()
        context = {'form': form}
        return render(request, template, context)
