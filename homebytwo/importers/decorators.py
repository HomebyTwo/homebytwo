from functools import wraps

from django.shortcuts import redirect
from django.urls import reverse

from ..routes.models import Athlete


def strava_required(view_func):
    """
    check for Strava authorization token and
    redirects to Strava connect if missing.
    """
    @wraps(view_func)
    def new_view_func(request, *args, **kwargs):

        # get or create the athlete for the request user
        athlete, created = Athlete.objects.get_or_create(user=request.user)

        # check athlete has a Strava token
        if not athlete.strava_token:
            return redirect(reverse('strava_connect'))

        # call the original function
        response = view_func(request, *args, **kwargs)
        return response

    return new_view_func


def switerland_mobility_required(view_func):
    """
    check for Switzerland Mobility Plus session cookies
    and redirects to login if missing.
    """
    @wraps(view_func)
    def new_view_func(request, *args, **kwargs):

        # Check if logged-in to Switzeland Mobility
        try:
            request.session['switzerland_mobility_cookies']

        # login cookies missing
        except KeyError:
            # redirect to the switzeland mobility login page
            return redirect('switzerland_mobility_login')

        # call the original function
        response = view_func(request, *args, **kwargs)
        return response

    return new_view_func
