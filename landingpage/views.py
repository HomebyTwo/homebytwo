from django.shortcuts import render


def home(request):
    # Project landing page
    return render(request, 'landingpage/home.html')
