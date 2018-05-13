from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured
from django.forms import EmailField, EmailInput, Form
from requests import codes, get, post, put


class EmailSubscriptionForm(Form):
    """
    Email subscribtion form for Mailchimp using Mail Chimp API v3
    """
    email = EmailField(
        label='Email Address',
        max_length=100,
        widget=EmailInput(attrs={
            'placeholder': 'Email',
            'required': True,
            'class': 'field',
        })
    )

    def signup_email(self, request):
        email = self.cleaned_data['email']

        # Do not signup email if MAILCHIMP_LIST_ID or API Key is empty
        if settings.MAILCHIMP_LIST_ID == '' or settings.MAILCHIMP_API_KEY == '':
            message = ('Please set the MAILCHIMP_LIST_ID and MAILCHIMP_API_KEY'
                       ' environment variables.')
            raise ImproperlyConfigured(message)

        # Prepare POST content
        payload = {'email_address': email, "status": "subscribed"}
        api_key = settings.MAILCHIMP_API_KEY
        list_id = settings.MAILCHIMP_LIST_ID
        auth = ('anything', api_key)

        # Retrieve datacenter from the end of the API key to construct URL
        datacenter = api_key[api_key.find('-')+1:]
        api_base_url = 'https://%s.api.mailchimp.com/3.0' % datacenter

        # POST to the list members to add a subscriber
        post_url = '/'.join([api_base_url, 'lists', list_id, 'members/'])
        response = post(post_url, json=payload, auth=auth)

        if response.status_code == codes.ok:
            message = 'Thank you! You are now subscribed with {}.'
            messages.success(request, message.format(email))
            return

        # Bad request email owner is already on the list
        if response.status_code == 400:

            # Get list member id from email
            search_url = api_base_url + '/search-members?query={}'
            response = get(search_url.format(email), auth=auth)

            # Find out if list member is subscribed
            status = response.json()['exact_matches']['members'][0]['status']

            # List member is already subscribed
            if status == 'subscribed':
                message = 'Thank you! You have subscribed with {}... again!'
                messages.success(request, message.format(email))
                return

            # Member is not currently subscribed, do it!
            else:
                member_id = response.json()['exact_matches']['members'][0]['id']
                put_url = post_url + member_id
                response = put(put_url, json=payload, auth=auth)

                if response.status_code == 200:
                    message = 'Thank you for signing up up again with {}.'
                    messages.success(request, message.format(email))
                    return

        response.raise_for_status()
