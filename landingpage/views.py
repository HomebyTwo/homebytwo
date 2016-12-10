from django.shortcuts import render, HttpResponse, HttpResponseRedirect

from .forms import EmailSubscriptionForm


def home(request):
    # Project landing page with signup form
    if request.method == 'POST':
        # create form and populate it with data from the request:
        form = EmailSubscriptionForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            response = form.signup_user()
            return HttpResponse(response)

    # if a GET (or any other method) we'll create a blank form
    else:
        form = EmailSubscriptionForm()

    return render(request, 'landingpage/home.html', {'form': form})


def get_email(request):
    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = EmailSubscriptionForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            response = form.signup_user()
            return HttpResponse(response)

    # if a GET (or any other method) we'll create a blank form
    else:
        form = EmailSubscriptionForm()

    return render(request, 'home.html', {'form': form})


def subsribe_user_to_mailchimp(request, email):
    """
    Subscribe user to mail chimp using Mail Chimp API v3
    params: email
    """
    pass
