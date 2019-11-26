from json import dumps as json_dumps

from django import forms
from django.conf import settings
from django.contrib import messages

from requests import Session, codes
from requests import exceptions as requests_exceptions


class SwitzerlandMobilityLogin(forms.Form):
    """
    This form prompts the user for his Switzerland Mobility Login
    and retrieves a session cookie.
    Credentials are not stored in the Database.
    """

    username = forms.CharField(
        label="Username",
        max_length=100,
        widget=forms.EmailInput(
            attrs={"placeholder": "Username on Switzeland Mobility Plus"}
        ),
    )

    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={"placeholder": "Password on Switzeland Mobility Plus"}
        ),
    )

    def retrieve_authorization_cookie(self, request):
        """
        Retrieves auth cookies from Switzeland Mobility
        and returns cookies or False
        The cookies are required to display a user's list of saved routes.

        Example response from the Switzerland Mobility login URL:
        {
          'loginErrorMsg': '',
          'userdata': {
            ...
          },
          'loginErrorCode': 200,
          'loginconfig': {
            ...
          }
        }

        Cookies returned by login URL in case of successful login:
        {'srv': 'xxx', 'mf-chmobil': 'xxx'}
        """

        login_url = settings.SWITZERLAND_MOBILITY_LOGIN_URL

        credentials = {
            "username": self.cleaned_data["username"],
            "password": self.cleaned_data["password"],
        }

        with Session() as session:
            # Try to login to map.wanderland.ch
            try:
                request = session.post(login_url, data=json_dumps(credentials))

            # catch the connection error and inform the user
            except requests_exceptions.ConnectionError:
                message = "Connection Error: could not connect to %s. " % login_url
                messages.error(request, message)
                return False

            # no connection error
            else:
                if request.status_code == codes.ok:

                    # log-in was successful, return cookies
                    if request.json()["loginErrorCode"] == 200:
                        cookies = dict(request.cookies)
                        message = "Successfully logged-in to Switzerland Mobility"
                        messages.success(request, message)
                        return cookies

                    # log-in failed
                    else:
                        message = request.json()["loginErrorMsg"]
                        messages.error(request, message)
                        return False

                # Some other server error
                else:
                    message = (
                        "Error %s: logging to Switzeland Mobility. "
                        "Try again later" % request.status_code
                    )
                    messages.error(request, message)
                    return False
