from django.shortcuts import render, HttpResponseRedirect

from .forms import EmailForm


def home(request):
    # Project landing page
    context = {
        'user': request.user,
    }
    return render(request, 'landingpage/home.html', context)


def get_email(request):
    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = EmailForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            # ...
            # redirect to a new URL:
            return HttpResponseRedirect('/thanks/')

    # if a GET (or any other method) we'll create a blank form
    else:
        form = EmailForm()

    return render(request, 'home.html', {'form': form})


def subsribe_user_to_mailchimp(request, email):
    """
    Subscribe user to mail chimp using Mail Chimp API v3
    params: email
    """
    pass
