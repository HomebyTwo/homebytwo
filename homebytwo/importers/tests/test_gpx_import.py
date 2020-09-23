from django import forms
from django.contrib.gis.geos import LineString
from django.urls import reverse

from pandas import DataFrame
from pytest import approx, raises
from pytest_django.asserts import assertRedirects, assertTemplateUsed

from ...routes.models import Route
from ..forms import GpxUploadForm

try:
    # Load LXML or fallback to cET or ET
    import lxml.etree as mod_etree  # type: ignore
except ImportError:
    try:
        import xml.etree.cElementTree as mod_etree  # type: ignore
    except ImportError:
        import xml.etree.ElementTree as mod_etree  # type: ignore


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
