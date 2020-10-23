from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode

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

        # logged-in users with no Strava account linked should blow-up
        except UserSocialAuth.DoesNotExist:
            raise StravaMissingCredentials

        # call the original function
        response = view_func(request, *args, **kwargs)
        return response

    return _wrapped_view


def remote_connection(view_func):
    """
    catch connection errors to remote services and handle
    them as gracefully as possible.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        try:
            response = view_func(request, *args, **kwargs)

        except ConnectionError as error:
            message = (
                "Could not connect to the remote server. Try again later: {}".format(
                    error
                )
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
            login_url = reverse("login")
            redirect_to = request.path
            return redirect(f"{login_url}?next={redirect_to}")

        except SwitzerlandMobilityMissingCredentials as error:
            messages.info(request, error)

            # redirect to Switzerland Mobility log-in page
            login_url = reverse("switzerland_mobility_login")

            # add route_id as a GET param if trying to import a route
            match = request.resolver_match
            if match.url_name == "import_route":
                route_id = match.kwargs["source_id"]
                params = urlencode({"route_id": route_id})
                return redirect(f"{login_url}?{params}")
            else:
                return redirect(login_url)

        # no exception, return the response from the decorated view
        else:
            return response

    return _wrapped_view
