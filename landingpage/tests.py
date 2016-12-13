from django.test import TestCase
from django.core.urlresolvers import reverse
from .forms import EmailSubscriptionForm
from django.conf import settings

import httpretty


class LandingpageTest(TestCase):

    # Construct MailChimp Base URI from the API key
    api_key = settings.MAILCHIMP_API_KEY
    datacenter = api_key[api_key.find('-')+1:]
    api_base_url = 'https://%s.api.mailchimp.com/3.0' % datacenter

    # Get MailChimp List ID from Settings
    list_id = settings.MAILCHIMP_LIST_ID

    # views
    def test_landingpage_home_view(self):
        content = "Home by Two"
        signup_form = EmailSubscriptionForm()
        url = reverse("home")
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(content in str(resp.content))
        self.assertTrue(str(signup_form['email']) in str(resp.content))

    def test_get_email_signup_view(self):
        url = reverse("email-signup")
        resp = self.client.get(url)

        self.assertRedirects(resp, "/")

    def test_post_email_signup_view_invalid(self):
        content = 'An error has occured'
        url = reverse("email-signup")
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(content in str(resp.content))

    @httpretty.activate
    def test_post_email_signup_view_not_subscribed(self):

        post_url = '/'.join([self.api_base_url, 'lists',
                            self.list_id, 'members/'])

        # Intercept request to MailChimp with httpretty
        httpretty.register_uri(httpretty.POST, post_url, status=200)

        data = {'email': 'example@example.com', 'list_id': self.list_id}
        content = 'subscribed'
        url = reverse("email-signup")
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(content in str(resp.content))

    @httpretty.activate
    def test_post_email_signup_view_already_subscribed(self):

        data = {'email': 'example@example.com', 'list_id': self.list_id}
        post_url = '/'.join([self.api_base_url, 'lists',
                            self.list_id, 'members/'])
        search_url = self.api_base_url + '/search-members?query=%s' % data['email']

        # Intercept request to MailChimp with httpretty
        httpretty.register_uri(httpretty.POST, post_url, status=400)
        json = '{"exact_matches":{"members":[{"status":"subscribed"}]}}'
        httpretty.register_uri(httpretty.GET, search_url, body=json)

        content = 'again!'
        url = reverse("email-signup")
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(content in str(resp.content))

    # forms
    def test_valid_form(self):
        email = 'example@example.com'
        list_id = '22345'
        data = {'email': email, 'list_id': list_id}
        form = EmailSubscriptionForm(data=data)
        self.assertTrue(form.is_valid())

    def test_invalid_form(self):
        email = 'example.com'
        list_id = ''
        data = {'email': email, 'list_id': list_id}
        form = EmailSubscriptionForm(data=data)
        self.assertFalse(form.is_valid())
