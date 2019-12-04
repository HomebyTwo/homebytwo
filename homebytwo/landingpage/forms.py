from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ImproperlyConfigured
from django.forms import EmailField, EmailInput, Form

from requests import codes, get, post, put

from .utils import get_mailchimp_post_url, get_mailchimp_search_url


class EmailSubscriptionForm(Form):
    """
    Email subscribtion form for Mailchimp using Mail Chimp API v3
    """

    email = EmailField(
        label="Email Address",
        max_length=100,
        widget=EmailInput(
            attrs={"placeholder": "Email", "required": True, "class": "field"}
        ),
    )

    def signup_email(self, request):
        email = self.cleaned_data["email"]

        # Do not signup email if MAILCHIMP_LIST_ID or API Key is empty
        if settings.MAILCHIMP_LIST_ID == "" or settings.MAILCHIMP_API_KEY == "":
            message = (
                "Please set the MAILCHIMP_LIST_ID and MAILCHIMP_API_KEY"
                " environment variables."
            )
            raise ImproperlyConfigured(message)

        # Prepare POST content
        post_data = {"email_address": email, "status": "subscribed"}
        post_url = get_mailchimp_post_url()
        mailchimp_auth = ("anything", settings.MAILCHIMP_API_KEY)

        # POST to the list members to add email as subscriber
        response = post(post_url, json=post_data, auth=mailchimp_auth)

        if response.status_code == codes.ok:
            message = "Thank you! You are now subscribed with {email}."
            messages.success(request, message.format(email=email))
            return

        # Bad request email owner is already on the list
        if response.status_code == 400:

            # Find out if email is aleady subscribed to the list
            response = get(get_mailchimp_search_url(email), auth=mailchimp_auth)
            status = response.json()["exact_matches"]["members"][0]["status"]

            # List member is already subscribed
            if status == "subscribed":
                message = "Thank you! You have subscribed with {email}... again!"
                messages.success(request, message.format(email=email))
                return

            # Member is not currently subscribed, do it!
            else:
                member_id = response.json()["exact_matches"]["members"][0]["id"]
                put_url = post_url + member_id
                response = put(put_url, json=post_data, auth=mailchimp_auth)

                if response.status_code == 200:
                    message = "Thank you for signing up up again with {email}."
                    messages.success(request, message.format(email=email))
                    return

        response.raise_for_status()
