from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from requests.exceptions import ConnectionError
from social_django.models import UserSocialAuth
from stravalib.exc import AccessUnauthorized as StravaAccessUnauthorized

from .exceptions import (
    StravaMissingCredentials,
    SwitzerlandMobilityError,
    SwitzerlandMobilityMissingCredentials,
)


def strava_required(view_func):
    """
    check for Strava authorization token and
    redirects to Strava connect if missing.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):

        # check if the user has an associated Strava account
        try:
            request.user.social_auth.get(provider="strava")

        # redirect to login with strava page
        except UserSocialAuth.DoesNotExist:
            message = "You are not connected to Strava."
            messages.error(request, message)
            return redirect(
                "{login_url}?next={next}".format(
                    login_url=reverse("login"), next=request.path
                )
            )

        # call the original function
        response = view_func(request, *args, **kwargs)
        return response

    return _wrapped_view


def remote_connection(view_func):
    """
    cacth connection errors to remote services and handle
    them as gracefully as possible.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            response = view_func(request, *args, **kwargs)

        except ConnectionError as error:
            message = "Could not connect to the remote server. Try again later: {}".format(
                error
            )
            messages.error(request, message)
            return redirect("routes:routes")

        except SwitzerlandMobilityError as error:
            message = "Error connecting to Switzerland Mobility Plus: {}".format(error)
            messages.error(request, message)
            return redirect("routes:routes")

        except (StravaAccessUnauthorized, StravaMissingCredentials):
            message = "There was an issue connecting to Strava. Try again later!"
            messages.error(request, message)
            return redirect(
                "{login_url}?next={next}".format(
                    login_url=reverse("login"), next=request.path
                )
            )

        except SwitzerlandMobilityMissingCredentials:
            message = "Please connect to Switzerland Mobility, first."
            messages.info(request, message)
            return redirect("switzerland_mobility_login")
        else:
            return response

    return _wrapped_view
