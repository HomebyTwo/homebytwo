from django import forms

import django_tables2 as tables
from django_tables2 import Column, URLColumn, CheckBoxColumn

from .models import Activity


class HiddenInputColumn(Column):
    def __init__(self, *args, **kwargs):
        kwargs["attrs"] = {
            "th": {"style": "display:none;"},
            "td": {"style": "display:none;"},
            "tf": {"style": "display:none;"},
        }
        super().__init__(*args, **kwargs)

    def render(self, value):
        form_widget = forms.HiddenInput()
        return form_widget.render(name=self.verbose_name, value=value)


class ActivityTable(tables.Table):
    class Meta:
        model = Activity
        fields = (
            "id",
            "activity_type",
            "start_date",
            "name",
            "total_elevation_gain",
            "distance",
            "get_strava_url",
            "use_for_prediction",
        )
        template_name = "django_tables2/semantic.html"

    id = HiddenInputColumn(verbose_name='id', accessor='pk')
    use_for_prediction = CheckBoxColumn(checked=lambda value, record: value)
    get_strava_url = URLColumn(
        orderable=False,
        text="view on Strava",
        linkify=lambda record: record.get_strava_url(),
    )
