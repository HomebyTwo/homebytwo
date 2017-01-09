from django import forms
from django.conf import settings

import json
import requests


class SwitzerlandMobilityLogin(forms.Form):
    """
    This form prompts the user for his Switzerland Mobility Login
    and retrieves a session cookie.
    Credentials are not stored in the Database
    """
    username = forms.CharField(
        label='Username', max_length=100,
        widget=forms.EmailInput(attrs={'placeholder': 'Username'}))

    password = forms.CharField(label='Password', widget=forms.PasswordInput)

    def retrieve_authorization_cookie(self):
        '''
        Retrieves auth cookies from Switzeland Mobility and returns a tulple:
        (cookies or False, response = {'error': bool, 'message': str})
        The cookies are required to display the list of saved routes.

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
        r = requests.post(login_url, data=json.dumps(credentials))

        if r.status_code == requests.codes.ok:

            # log-in was successful, return cookies
            if r.json()['loginErrorCode'] == 200:
                cookies = dict(r.cookies)
                error = False
                message = "Successfully logged in to Switzerland Mobility"
                return cookies, {'error': error, 'message': message}

            # log-in failed
            else:
                error = True
                message = r.json()['loginErrorMsg']
                return False, {'error': error, 'message': message}

        # Some other connection error
        else:
            error = True
            message = (
                'Error connecting to Switzeland Mobility. '
                'Try again later'
            )

            return False, {'error': error, 'message': message}
