from json import dumps

from django.shortcuts import HttpResponse, redirect, render

from .forms import EmailSubscriptionForm


def home(request):

    # Include email signup form
    context = {
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

        # The form data is invalid. Get the errors.
        else:
            message = 'An error has occured. '

            for error in form.errors:
                message += error + ': '
                for error_message in form.errors[error]:
                    message += error_message

            response = {'error': True, 'message': message}

        # If the POST was AJAX, return a JSON
        if request.is_ajax():
            return HttpResponse(dumps(response))

        # If the POST is not AJAX, print the template
        else:
            return render(request,
                          'landingpage/email_signup_confirm.html',
                          response)

    # if it was a GET request we just redirect to the homepage
    else:
        return redirect('home')


def register(request):

    # Include email signup form
    context = {
        'form': EmailSubscriptionForm(),
    }

    return render(request, 'landingpage/register.html', context)
