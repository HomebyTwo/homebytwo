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
    if request.method == 'POST' and request.is_ajax():
        # create a form instance and populate it with data from the request:
        form = EmailSubscriptionForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            response = form.signup_email()
            return HttpResponse(json.dumps(response))

    # if a GET (or any other method) we'll redirect to the homepage
    else:
        return HttpResponseRedirect('/')
