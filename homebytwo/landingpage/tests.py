import httpretty
from django.conf import settings
from django.core.urlresolvers import reverse
from django.test import TestCase, override_settings

from .forms import EmailSubscriptionForm


@override_settings(MAILCHIMP_API_KEY='dummy-usXX',
                   MAILCHIMP_LIST_ID='123456')
class LandingpageTest(TestCase):

    # Construct MailChimp Base URI from the API key
    def get_api_base_url(self):
        api_key = settings.MAILCHIMP_API_KEY
        datacenter = api_key[api_key.find('-')+1:]
        return 'https://%s.api.mailchimp.com/3.0' % datacenter

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
        with self.settings(GTM_CONTAINER_ID='GTM-1234'):
            url = reverse("home")
            resp = self.client.get(url)
            self.assertTrue('GTM-1234' in str(resp.content))

    def test_empty_gtm_container_id_not_in_template(self):
        with self.settings(GTM_CONTAINER_ID=''):
            gtm_url = 'https://www.googletagmanager.com/'
            url = reverse("home")
            resp = self.client.get(url)
            self.assertFalse(gtm_url in str(resp.content))

    # Register
    def test_landingpage_register_view(self):
        content = "Even though we would love you to register right now."
        signup_form = EmailSubscriptionForm()
        url = reverse("register")
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(content in str(resp.content))
        self.assertTrue(str(signup_form['email']) in str(resp.content))

    # Email signup
    def test_get_email_signup_view(self):
        url = reverse("email_signup")
        resp = self.client.get(url)

        self.assertRedirects(resp, "/")

    def test_post_email_signup_view_invalid(self):
        content = 'An error has occured'
        url = reverse("email_signup")
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(content in str(resp.content))

    # Mailchimp API
    def test_exception_if_mailchimp_list_id_not_set(self):
        with self.settings(MAILCHIMP_LIST_ID=''):
            data = {'email': 'example@example.com',
                    'list_id': settings.MAILCHIMP_LIST_ID}
            content = 'Please set the MAILCHIMP_LIST_ID and MAILCHIMP_API_KEY'
            url = reverse("email_signup")
            resp = self.client.post(url, data)

            self.assertEqual(resp.status_code, 200)
            self.assertTrue(content in str(resp.content))

    def test_exception_if_mailchimp_api_key_not_set(self):
        with self.settings(MAILCHIMP_API_KEY=''):
            data = {'email': 'example@example.com',
                    'list_id': settings.MAILCHIMP_LIST_ID}
            content = 'Please set the MAILCHIMP_LIST_ID and MAILCHIMP_API_KEY'
            url = reverse("email_signup")
            resp = self.client.post(url, data)

            self.assertEqual(resp.status_code, 200)
            self.assertTrue(content in str(resp.content))

    def test_post_email_signup_view_not_subscribed(self):
        api_base_url = self.get_api_base_url()
        post_url = '/'.join([api_base_url, 'lists',
                            settings.MAILCHIMP_LIST_ID, 'members/'])

        # Intercept request to MailChimp with httpretty
        httpretty.enable()
        httpretty.register_uri(httpretty.POST, post_url, status=200)

        data = {'email': 'example@example.com',
                'list_id': settings.MAILCHIMP_LIST_ID}
        content = 'subscribed'
        url = reverse("email_signup")
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(content in str(resp.content))

        httpretty.disable()
        httpretty.reset()

    def test_post_email_signup_view_already_subscribed(self):
        api_base_url = self.get_api_base_url()
        data = {'email': 'example@example.com',
                'list_id': settings.MAILCHIMP_LIST_ID}
        post_url = '/'.join([api_base_url, 'lists',
                            settings.MAILCHIMP_LIST_ID, 'members/'])
        search_url = api_base_url + '/search-members?query=%s' % data['email']

        # Intercept request to MailChimp with httpretty
        httpretty.enable()
        httpretty.register_uri(httpretty.POST, post_url, status=400)

        json = '{"exact_matches":{"members":[{"status":"subscribed"}]}}'
        httpretty.register_uri(httpretty.GET, search_url, body=json)

        content = 'again!'
        url = reverse("email_signup")

        resp = self.client.post(url, data)

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(content in str(resp.content))

        httpretty.disable()
        httpretty.reset()

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
