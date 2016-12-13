from django.shortcuts import render, HttpResponse, HttpResponseRedirect

from .forms import EmailSubscriptionForm
import json


def home(request):
    context = {
        # Include email signup form
        'form': EmailSubscriptionForm(),
    }

    return render(request, 'landingpage/home.html', context)


def email_signup(request):
    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = EmailSubscriptionForm(request.POST)

        # Prepare the repsonse.
        # The posted form data is valid, get the response from MailChimp!
        if form.is_valid():
            response = form.signup_email()

        # The form data is invalid.
        else:
            response = {'error': True,
                        'message': 'An error has occured '
                                   'with your email subscription.'}

        # If the POST was AJAX, return a JSON
        if request.is_ajax():
            return HttpResponse(json.dumps(response))

        # If the POST is not AJAX, print the template
        else:
            return render(request,
                          'landingpage/email_signup_confirm.html',
                          response)

    # if it was a GET request we just redirect to the homepage
    else:
        return HttpResponseRedirect('/')
