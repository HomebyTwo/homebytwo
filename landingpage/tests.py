from django.test import TestCase
from django.core.urlresolvers import reverse
from .forms import EmailSubscriptionForm
from django.conf import settings

from django.core.exceptions import ImproperlyConfigured

import httpretty


class LandingpageTest(TestCase):

    # Construct MailChimp Base URI from the API key
    api_key = 'dummy-usXX'
    datacenter = api_key[api_key.find('-')+1:]
    api_base_url = 'https://%s.api.mailchimp.com/3.0' % datacenter
    list_id = '123456'

    def setUp(self):
        settings.MAILCHIMP_API_KEY = self.api_key
        settings.MAILCHIMP_LIST_ID = self.list_id

    # Set MAILCHIMP List ID
    settings.MAILCHIMP_LIST_ID = '123456'

    # Home view
    def test_landingpage_home_view(self):
        content = "Home by Two"
        signup_form = EmailSubscriptionForm()
        url = reverse("home")
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(content in str(resp.content))
        self.assertTrue(str(signup_form['email']) in str(resp.content))

    def test_gtm_container_id_in_template(self):
        settings.GTM_CONTAINER_ID = 'GTM-1234'

        url = reverse("home")
        resp = self.client.get(url)

        self.assertTrue(settings.GTM_CONTAINER_ID in str(resp.content))

    def test_empty_gtm_container_id_not_in_template(self):
        settings.GTM_CONTAINER_ID = ''
        gtm_url = 'https://www.googletagmanager.com/'

        url = reverse("home")
        resp = self.client.get(url)

        self.assertFalse(gtm_url in str(resp.content))

    # Email signup
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

    # Mailchimp API
    def test_exception_if_mailchimp_list_id_not_set(self):
        settings.MAILCHIMP_LIST_ID = ''

        url = reverse("home")
        self.assertRaises(ImproperlyConfigured, self.client.get, url)

    def test_exception_if_mailchimp_api_key_not_set(self):
        settings.MAILCHIMP_API_KEY = ''

        url = reverse("email-signup")
        self.assertRaises(ImproperlyConfigured, self.client.post, url)

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
