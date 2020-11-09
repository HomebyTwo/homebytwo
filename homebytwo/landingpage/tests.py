import json

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

import responses
from requests.exceptions import ConnectionError

from .forms import EmailSubscriptionForm
from .utils import get_mailchimp_post_url, get_mailchimp_search_url


@override_settings(MAILCHIMP_API_KEY="dummy-usXX", MAILCHIMP_LIST_ID="123456")
class LandingpageTest(TestCase):

    # Home view
    def test_landingpage_home_view(self):
        content = "Homebytwo"
        signup_form = EmailSubscriptionForm()
        url = reverse("home")
        response = self.client.get(url)

        self.assertContains(response, content)
        self.assertContains(response, signup_form["email"])

    @override_settings(GTM_CONTAINER_ID="GTM-1234")
    def test_gtm_container_id_in_template(self):
        gtm_id = settings.GTM_CONTAINER_ID
        url = reverse("home")
        response = self.client.get(url)
        self.assertContains(response, gtm_id)

    @override_settings(GTM_CONTAINER_ID="")
    def test_empty_gtm_container_id_not_in_template(self):
        gtm_url = "https://www.googletagmanager.com/"
        url = reverse("home")
        resp = self.client.get(url)
        self.assertFalse(gtm_url in str(resp.content))

    # Email signup
    def test_get_email_signup_view(self):
        url = reverse("email_signup")
        response = self.client.get(url)
        field_type = '<input type="email"'
        placeholder = 'placeholder="Email"'

        self.assertContains(response, field_type)
        self.assertContains(response, placeholder)

    def test_post_email_signup_view_invalid(self):
        content = '<div class="field-error">'
        url = reverse("email_signup")
        response = self.client.post(url)

        self.assertContains(response, content)

    # Mailchimp API
    @override_settings(MAILCHIMP_LIST_ID="")
    def test_exception_if_mailchimp_list_id_not_set(self):
        data = {
            "email": "example@example.com",
            "list_id": settings.MAILCHIMP_LIST_ID,
        }
        content = "Please set the MAILCHIMP_LIST_ID and MAILCHIMP_API_KEY"
        url = reverse("email_signup")
        response = self.client.post(url, data)

        self.assertContains(response, content)

    @override_settings(MAILCHIMP_LIST_ID="")
    def test_exception_if_mailchimp_api_key_not_set(self):
        data = {
            "email": "example@example.com",
            "list_id": settings.MAILCHIMP_LIST_ID,
        }
        content = "Please set the MAILCHIMP_LIST_ID and MAILCHIMP_API_KEY"
        url = reverse("email_signup")
        response = self.client.post(url, data)

        self.assertContains(response, content)

    @responses.activate
    def test_post_email_signup_view_success(self):
        email = "example@example.com"
        data = {"email": email, "list_id": settings.MAILCHIMP_LIST_ID}
        mailchimp_post_url = get_mailchimp_post_url()
        message = "Thank you! You are now subscribed with {email}.".format(email=email)

        # Intercept request to MailChimp
        responses.add(responses.POST, mailchimp_post_url, status=200)

        url = reverse("email_signup")
        response = self.client.post(url, data)
        redirected_response = self.client.post(url, data, follow=True)

        self.assertRedirects(response, "/")
        self.assertContains(redirected_response, message)

    @responses.activate
    def test_post_email_signup_view_already_subscribed(self):
        email = "example@example.com"
        data = {"email": email, "list_id": settings.MAILCHIMP_LIST_ID}
        mailchimp_post_url = get_mailchimp_post_url()
        mailchimp_search_url = get_mailchimp_search_url(email=email)
        json_response = json.dumps(
            {"exact_matches": {"members": [{"status": "subscribed"}]}}
        )
        message = "Thank you! You have subscribed with {email}... again!".format(
            email=email
        )

        # Intercept request to MailChimp

        responses.add(
            responses.POST, mailchimp_post_url, status=400, match_querystring=False
        )
        responses.add(responses.GET, mailchimp_search_url, body=json_response)

        url = reverse("email_signup")
        response = self.client.post(url, data)
        redirected_response = self.client.post(url, data, follow=True)

        self.assertRedirects(response, "/")
        self.assertContains(redirected_response, message)

    @responses.activate
    def test_post_email_signup_exists_but_not_subscribed(self):
        email = "example@example.com"
        data = {"email": email, "list_id": settings.MAILCHIMP_LIST_ID}
        member_id = "123456"

        mailchimp_post_url = get_mailchimp_post_url()
        mailchimp_search_url = get_mailchimp_search_url(email=email)
        mailchimp_put_url = mailchimp_post_url + member_id

        json_response = json.dumps(
            {
                "exact_matches": {
                    "members": [{"id": member_id, "status": "unsubscribed"}]
                }
            }
        )
        message = "Thank you for signing up up again with {email}.".format(email=email)

        # Intercept request to MailChimp
        responses.add(responses.POST, mailchimp_post_url, status=400, match_querystring=False)
        responses.add(responses.GET, mailchimp_search_url, body=json_response)
        responses.add(responses.PUT, mailchimp_put_url, status=200)

        url = reverse("email_signup")
        response = self.client.post(url, data)
        redirected_response = self.client.post(url, data, follow=True)

        self.assertRedirects(response, "/")
        self.assertContains(redirected_response, message)

    @responses.activate
    def test_post_email_signup_exists_but_not_subscribed_error(self):
        email = "example@example.com"
        data = {"email": email, "list_id": settings.MAILCHIMP_LIST_ID}
        member_id = "123456"

        mailchimp_post_url = get_mailchimp_post_url()
        mailchimp_search_url = get_mailchimp_search_url(email=email)
        mailchimp_put_url = mailchimp_post_url + member_id

        json_response = json.dumps(
            {
                "exact_matches": {
                    "members": [{"id": member_id, "status": "unsubscribed"}]
                }
            }
        )
        message = "MailChimp Error: "

        # Intercept request to MailChimp
        responses.add(responses.POST, mailchimp_post_url, status=400)
        responses.add(responses.GET, mailchimp_search_url, body=json_response)
        responses.add(responses.PUT, mailchimp_put_url, status=400)

        url = reverse("email_signup")
        response = self.client.post(url, data)

        self.assertContains(response, message)

    @responses.activate
    def test_post_email_signup_connection_error(self):
        mailchimp_post_url = get_mailchimp_post_url()
        data = {
            "email": "example@example.com",
            "list_id": settings.MAILCHIMP_LIST_ID,
        }
        message = "MailChimp Error:"

        # Intercept request to MailChimp
        responses.add(
            responses.POST,
            mailchimp_post_url,
            body=ConnectionError("Connection error."),
        )

        url = reverse("email_signup")
        response = self.client.post(url, data)

        self.assertContains(response, message)

    # forms
    def test_valid_form(self):
        email = "example@example.com"
        list_id = "22345"
        data = {"email": email, "list_id": list_id}
        form = EmailSubscriptionForm(data=data)
        self.assertTrue(form.is_valid())

    def test_invalid_form(self):
        email = "example.com"
        list_id = ""
        data = {"email": email, "list_id": list_id}
        form = EmailSubscriptionForm(data=data)
        self.assertFalse(form.is_valid())
