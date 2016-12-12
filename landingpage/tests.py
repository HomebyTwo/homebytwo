from django.test import TestCase
from django.core.urlresolvers import reverse
from .forms import EmailSubscriptionForm


class LandingpageTest(TestCase):
    # models test

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

    def test_post_email_signup_view(self):
        content = ''
        url = reverse("email-signup")
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(content in resp.content)

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
