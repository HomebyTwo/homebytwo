from django import forms


class SwitzerlandMobilityLogin(forms.Form):
    """
    This form prompts the user for his Switzerland Mobility Login
    and retrieves a session cookie. Credentials are not stored in the
    Database
    """
    username = forms.CharField(label='Username', max_length=100,
                               widget=forms.EmailInput(
                                    attrs={'placeholder': 'Username'}))

    password = forms.CharField(label='Password', widget=forms.PasswordInput)
