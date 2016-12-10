from django import forms
from django.conf import settings

import requests


class EmailSubscriptionForm(forms.Form):
    """
    Email subscribtion form for Mailchimp using Mail Chimp API v3
    """
    email = forms.EmailField(label='Email Address', max_length=100)
    list_id = forms.CharField(widget=forms.HiddenInput, initial='f1300adfdc')
    error_css_class = 'error'
    required_css_class = 'required'

    def signup_email(self):
        email = self.cleaned_data['email']
        list_id = self.cleaned_data['list_id']

        # Prepare POST content
        payload = {'email_address': email, "status": "subscribed"}
        api_key = settings.MAILCHIMP_API_KEY
        auth = ('anything', api_key)

        # Retrieve datacenter from the end of the API key to construct URL
        datacenter = api_key[api_key.find('-')+1:]
        api_base_url = 'https://%s.api.mailchimp.com/3.0' % datacenter

        # POST to the list members to add a subscriber
        post_url = '/'.join([api_base_url, 'lists', list_id, 'members/'])
        resp = requests.post(post_url, json=payload, auth=auth)

        if resp.status_code == 200:
            return 'subscribed'

        # Bad request email owner is already a subscriber
        if resp.status_code == 400:

            # Get list member id from email
            search_url = api_base_url + '/search-members?query=%s' % email
            resp = requests.get(search_url, auth=auth)

            # If the member is not currently subscribed, do it!
            if resp.json()['exact_matches']['members'][0]['status'] != 'subscribed':
                member_id = resp.json()['exact_matches']['members'][0]['id']
                put_url = post_url + member_id
                resp = requests.put(put_url, json=payload, auth=auth)
                return 'resubscribed'

            # List member is already subscribed
            else:
                return 'already subscribed'

        else:
            return 'API error'
