from django.contrib.gis.geos import LineString
from django.urls import reverse

from pandas import DataFrame
from pytest import approx
from pytest_django.asserts import (
    assertContains,
    assertNotContains,
    assertRedirects,
    assertTemplateUsed,
)

from ...routes.models import Route
from ...routes.tests.factories import RouteFactory
from ..forms import GpxUploadForm


def test_gpx_upload_form(uploaded_file):
    gpx_file = uploaded_file("grammont.gpx")

    form = GpxUploadForm(files={"gpx": gpx_file})
    assert form.is_valid()

    route = form.save(commit=False)
    assert route.name == "Grammont et Alamont"  # name in GPX file
    assert isinstance(route, Route)
    assert isinstance(route.data, DataFrame)
    assert isinstance(route.geom, LineString)
    assert route.total_distance == approx(6937.309)
    assert route.total_elevation_gain == approx(827.734)
    assert route.total_elevation_loss == approx(369.083)


def test_gpx_upload_form_wrong_file(uploaded_file):
    gpx_file = uploaded_file("text.txt")
    form = GpxUploadForm(files={"gpx": gpx_file})
    assert form.is_valid() is False


def test_gpx_upload_form_bad_schema(uploaded_file):
    gpx_file = uploaded_file("bad_schemaLocation.gpx")
    form = GpxUploadForm(files={"gpx": gpx_file})

    assert form.is_valid() is False


def test_gpx_upload_form_empty(uploaded_file):
    gpx_file = uploaded_file("empty.gpx")
    form = GpxUploadForm(files={"gpx": gpx_file})

    assert form.is_valid() is False


def test_gpx_upload_form_one_point(uploaded_file):
    gpx_file = uploaded_file("one_point.gpx")
    form = GpxUploadForm(files={"gpx": gpx_file})

    assert form.is_valid() is False


def test_upload_gpx_view(athlete, client, uploaded_file):
    gpx_file = uploaded_file("grammont.gpx")
    url = reverse("upload_gpx")
    response = client.post(url, data={"gpx": gpx_file})

    route = Route.objects.get(name="Grammont et Alamont")
    redirect_url = reverse("routes:edit", kwargs={"pk": route.pk})

    assert route.athlete == athlete
    assertRedirects(response, redirect_url)


def test_upload_gpx_view_empty(athlete, client, uploaded_file):
    gpx_file = uploaded_file("empty.gpx")
    url = reverse("upload_gpx")
    response = client.post(url, data={"gpx": gpx_file})
    assertTemplateUsed(response, "importers/index.html")


def test_get_gpx_route_no_update_button(athlete, client):
    route = RouteFactory(data_source="homebytwo", athlete=athlete)
    response = client.get(route.get_absolute_url())
    assertContains(response, route.delete_url)
    assertNotContains(response, route.get_absolute_url("update"))


def test_get_update_gpx_route(athlete, client):
    route = RouteFactory(data_source="homebytwo", athlete=athlete)
    response = client.get(route.update_url)
    assert response.status_code == 404
