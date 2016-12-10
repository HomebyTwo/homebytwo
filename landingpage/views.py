from django.shortcuts import render, HttpResponse

from .forms import EmailSubscriptionForm


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
        # check whether it's valid:
        if form.is_valid():
            response = form.signup_email()
            return HttpResponse(response)

    # if a GET (or any other method) we'll create a blank form
    else:
        form = EmailSubscriptionForm()

    return render(request, 'home.html', {'form': form})
