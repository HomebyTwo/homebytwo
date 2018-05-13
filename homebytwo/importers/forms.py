from json import dumps as json_dumps

from django import forms
from django.conf import settings
from django.contrib import messages
from requests import exceptions as requests_exceptions
from requests import codes, post

from ..routes.forms import RouteForm
from ..routes.models import Place, Route


class ImportersRouteForm(RouteForm):

    class Meta:
        model = Route
        fields = [
            'activity_type',
            'data',
            'end_place',
            'geom',
            'length',
            'name',
            'source_id',
            'start_place',
            'totaldown',
            'totalup',
        ]

        # Do not display the following fields in the form.
        # These values are retrieved from the original route
        widgets = {
            'name': forms.HiddenInput,
            'source_id': forms.HiddenInput,
            'totalup': forms.HiddenInput,
            'totaldown': forms.HiddenInput,
            'length': forms.HiddenInput,
            'geom': forms.HiddenInput,
        }

    class PlaceChoiceField(forms.ModelChoiceField):
        def label_from_instance(self, obj):
            return '%s - %s.' % (
                obj.name,
                obj.get_place_type_display()
            )

    start_place = PlaceChoiceField(
        queryset=Place.objects.all(),
        empty_label=None,
        required=False,
    )

    end_place = PlaceChoiceField(
        queryset=Place.objects.all(),
        empty_label=None,
        required=False,
    )


class SwitzerlandMobilityLogin(forms.Form):
    """
    This form prompts the user for his Switzerland Mobility Login
    and retrieves a session cookie.
    Credentials are not stored in the Database.
    """
    username = forms.CharField(
        label='Username', max_length=100,
        widget=forms.EmailInput(attrs={
            'placeholder': 'Username on Switzeland Mobility Plus',
        }))

    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Password on Switzeland Mobility Plus',
        }))

    def retrieve_authorization_cookie(self, request):
        '''
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
        '''

        login_url = settings.SWITZERLAND_MOBILITY_LOGIN_URL

        credentials = {
            "username": self.cleaned_data['username'],
            "password": self.cleaned_data['password'],
        }

        # Try to login to map.wanderland.ch
        try:
            r = post(login_url, data=json_dumps(credentials))

        # catch the connection error and inform the user
        except requests_exceptions.ConnectionError:
            message = "Connection Error: could not connect to %s. " % login_url
            messages.error(request, message)
            return False

        # no exception
        else:
            if r.status_code == codes.ok:

                # log-in was successful, return cookies
                if r.json()['loginErrorCode'] == 200:
                    cookies = dict(r.cookies)
                    message = "Successfully logged-in to Switzerland Mobility"
                    messages.success(request, message)
                    return cookies

                # log-in failed
                else:
                    message = r.json()['loginErrorMsg']
                    messages.error(request, message)
                    return False

            # Some other server error
            else:
                message = (
                    'Error %s: logging to Switzeland Mobility. '
                    'Try again later' % r.status_code
                )
                messages.error(request, message)
                return False
