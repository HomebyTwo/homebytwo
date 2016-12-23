from django import forms

import requests


class SwitzerlandMobilityLogin(forms.Form):
    """
    This form prompts the user for his Switzerland Mobility Login
    and retrieves a session cookie.
    Credentials are not stored in the Database
    """
    username = forms.CharField(label='Username', max_length=100,
                               widget=forms.EmailInput(
                                    attrs={'placeholder': 'Username'}))

    password = forms.CharField(label='Password', widget=forms.PasswordInput)

    def retrieve_authorization_cookie(self):

        login_url = 'https://map.wanderland.ch/user/login'

        # TODO: store in the database for each user
        credentials = {
                        "username": self.username,
                        "password": self.password
                    }

        # login to map.wanderland.ch
        r = requests.post(login_url, data=json.dumps(credentials))

        # save cookies
        if r.status_code == requests.codes.ok:
            cookies = r.cookies
        else:
            pass
