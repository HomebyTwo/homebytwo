from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.generic.edit import UpdateView


from .models import Route, RoutePlace


def index(request):
    routes = Route.objects.order_by('name')
    context = {
        'routes': routes,
    }
    return render(request, 'routes/index.html', context)


def detail(request, pk):
    route = Route.objects.get(id=pk)
    places = RoutePlace.objects.filter(route=pk)
    for place in places:
        place.schedule = route.get_time_data_from_line_location(
                    place.line_location,
                    'schedule'
        )

    context = {
        'route': route,
        'places': places
    }
    return render(request, 'routes/detail.html', context)


@method_decorator(login_required, name='dispatch')
class ImageFormView(UpdateView):
    model = Route
    fields = ['name', 'image']

    template_name_suffix = '_image_form'

    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.
        import pdb; pdb.set_trace()
        return super(ImageFormView, self).form_valid(form)


@login_required
def edit(request, route_id):
    response = "You are looking at the edit page of route %s"
    return HttpResponse(response % route_id)


@login_required
def importers(request):
    return render(request, 'routes/importers.html')
