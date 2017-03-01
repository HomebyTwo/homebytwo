from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.forms import modelformset_factory, HiddenInput
from django.db import transaction, IntegrityError
from django.contrib.auth.decorators import login_required

from .models import StravaRoute, SwitzerlandMobilityRoute
from .forms import SwitzerlandMobilityLogin, SwitzerlandMobilityRouteForm
from routes.models import Athlete, Place, RoutePlace

from stravalib.client import Client as StravaClient


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
    """
    Main import page for Switzerland Mobility.
    There is a modelform for the route and a modelformset
    for the places found along the route.

    The route form is instanciated with the json data retrieved from
    Switzerland Mobility.

    The places_form is populated with places found along the retrieved route
    using a query to the database.
    """

    # cast route id from url to integer
    source_id = int(source_id)

    # default values for variables passed to the request context
    route = False
    places = False
    route_form = False
    places_form = False
    response = {
        'error': False,
        'message': '',
    }

    # define fields of the places modelformset used in both GET and POST
    places_form_fields = ['place', 'line_location', 'altitude_on_route']

    # with a POST request try to import route and places
    if request.method == 'POST':

        # populate the route form with POST data
        route_form = SwitzerlandMobilityRouteForm(
            request.POST,
            prefix='route',
        )

        # validate route form and return errors if any
        if not route_form.is_valid():
            response['error'] = True
            response['message'] += str(route_form.errors)

        # Places form
        # create form class with modelformset_factory
        PlacesForm = modelformset_factory(
            RoutePlace,
            fields=places_form_fields,
        )

        # intstantiate form with modelformset Class and POST data
        places_form = PlacesForm(
            request.POST,
            prefix='places',
        )

        # validate places form and return errors if any
        if not places_form.is_valid():
            response['error'] = True
            response['message'] += str(places_form.errors)

        # If both forms validate, save the route and places
        if not response['error']:

            # create the route with the route_form
            new_route = route_form.save(commit=False)
            # set user for route
            new_route.user = request.user

            # create the route places from the places_form
            route_places = places_form.save(commit=False)

            try:
                with transaction.atomic():
                    new_route.save()

                    for route_place in route_places:
                        # set RoutePlace.route to newly saved route
                        route_place.route = new_route
                        route_place.save()

            except IntegrityError as error:
                response = {
                    'error': True,
                    'message': 'Integrity Error: %s. ' % error,
                }

        # Success! redirect to the page of the newly imported route
        if not response['error']:
            redirect_url = reverse('routes:detail', args=(new_route.id,))
            return HttpResponseRedirect(redirect_url)

    # GET request
    else:
        # fetch route details from Switzerland Mobility
        route, response = SwitzerlandMobilityRoute.objects. \
            get_remote_route(source_id)

        # route details succesfully retrieved
        if route:

            # add user to check if route has already been imported
            route.user = request.user

            # compute elevation and schedule data
            route.calculate_cummulative_elevation_differences()
            route.calculate_projected_time_schedule()

            # populate the route_form with route details
            route_form = SwitzerlandMobilityRouteForm(
                instance=route,
                prefix='route',
            )

            # find places to display in the select
            # for start, finish points.
            route_form.fields['start_place'].queryset = \
                route.get_closest_places_along_line(
                    line_location=0,  # start
                    max_distance=200,
                )

            route_form.fields['end_place'].queryset = \
                route.get_closest_places_along_line(
                    line_location=1,  # finish
                    max_distance=200,
                )

            # find checkpoints along the route
            places = Place.objects.get_places_from_line(
                route.geom,
                max_distance=50
            )

            # enrich checkpoint data with information
            checkpoints = []
            for place in places:

                altitude_on_route = route.get_distance_data_from_line_location(
                    place.line_location, 'altitude')
                place.altitude_on_route = altitude_on_route

                length_from_start = route.get_distance_data_from_line_location(
                    place.line_location, 'length')
                place.distance_from_start = length_from_start

                # get cummulative altitude gain
                total_up = route.get_distance_data_from_line_location(
                    place.line_location, 'total_up')
                place.total_up = total_up

                # get cummulative altitude loss
                total_down = route.get_distance_data_from_line_location(
                    place.line_location, 'total_down')
                place.total_down = total_down

                # get projected time schedula at place
                schedule = route.get_time_data_from_line_location(
                    place.line_location, 'schedule')
                place.schedule = schedule

                checkpoints.append(place)
                import pdb; pdb.set_trace()
            # convert checkpoints to RoutePlace objects
            route_places = [
                RoutePlace(
                    place=place,
                    line_location=place.line_location,
                    altitude_on_route=route.get_distance_data_from_line_location(
                        place.line_location, 'altitude').m,
                )
                for place in checkpoints
            ]

            # create form class with modelformset_factory
            PlacesForm = modelformset_factory(
                RoutePlace,
                fields=places_form_fields,
                extra=len(route_places),
                can_delete=True,
                widgets={
                    'place': HiddenInput,
                    'line_location': HiddenInput,
                    'altitude_on_route': HiddenInput,
                }
            )

            # instantiate form with initial data
            places_form = PlacesForm(
                prefix='places',
                queryset=RoutePlace.objects.none(),
                initial=[
                    {
                        'place': route_place.place,
                        'line_location': route_place.line_location,
                        'altitude_on_route': route_place.altitude_on_route,
                    }
                    for route_place in route_places
                ],
            )

            places = zip(checkpoints, places_form.forms)

    context = {
        'response': response,
        'route': route,
        'route_form': route_form,
        'places': places,
        'places_form': places_form,
    }

    template = 'importers/switzerland_mobility/detail.html'

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
