from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import redirect, render
from requests.exceptions import ConnectionError, HTTPError

from .forms import EmailSubscriptionForm, UserRegistrationForm


def home(request):

    # Include email signup form
    context = {
        'form': EmailSubscriptionForm(),
    }

    return render(request, 'landingpage/home.html', context)


def email_signup(request):

    template = 'landingpage/email_signup_confirm.html'

    # process the form data if it has been POSTed to this view
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = EmailSubscriptionForm(request.POST)

        # The posted form data is valid, try to subscribe the email to Mailchimp
        if form.is_valid():
            try:
                form.signup_email(request)

            # cannot connect to MailChimp
            except (HTTPError, ConnectionError) as error:
                message = "MailChimp Error: {}."
                messages.error(request, message.format(error))

            # missing MAILCHIMP_LIST_ID or API Key
            except ImproperlyConfigured as error:
                messages.error(request, error)

            # redirect home if there was no exception
            else:
                return redirect('home')

    # if it was a any other request, just display the empty form
    else:
        form = EmailSubscriptionForm()

    return render(request, template, {'form': form})


def register(request):

    template = 'landingpage/register.html'

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return redirect('routes:routes')
    else:
        form = UserRegistrationForm()

    return render(request, template, {'form': form})
