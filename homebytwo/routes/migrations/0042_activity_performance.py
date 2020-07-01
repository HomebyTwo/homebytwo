# Generated by Django 2.2.13 on 2020-07-01 20:45
import django.contrib.postgres.fields
from django.db import migrations, models

from numpy import array

import homebytwo.routes.fields


class Migration(migrations.Migration):

    dependencies = [
        ("routes", "0041_activity_streams"),
    ]

    operations = [
        migrations.RenameField(
            model_name="activity", old_name="totalup", new_name="total_elevation_gain",
        ),
        migrations.RemoveField(model_name="activityperformance", name="flat_param",),
        migrations.RemoveField(model_name="activityperformance", name="slope_param",),
        migrations.RemoveField(
            model_name="activityperformance", name="slope_squared_param",
        ),
        migrations.RemoveField(
            model_name="activityperformance", name="total_elevation_gain_param",
        ),
        migrations.RemoveField(model_name="activitytype", name="flat_param",),
        migrations.RemoveField(model_name="activitytype", name="slope_param",),
        migrations.RemoveField(model_name="activitytype", name="slope_squared_param",),
        migrations.RemoveField(
            model_name="activitytype", name="total_elevation_gain_param",
        ),
        migrations.AddField(
            model_name="activity",
            name="commute",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="activityperformance",
            name="cv_scores",
            field=homebytwo.routes.fields.NumpyArrayField(
                base_field=models.FloatField(), default=array([0.0, 0.0]), size=None
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="activityperformance",
            name="flat_parameter",
            field=models.FloatField(default=6.0),
        ),
        migrations.AddField(
            model_name="activityperformance",
            name="model_score",
            field=models.FloatField(default=0.0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="activityperformance",
            name="onehot_encoder_categories",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=django.contrib.postgres.fields.ArrayField(
                    base_field=models.CharField(max_length=50), size=None
                ),
                default=[["None"], ["None"]],
                size=None,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="activityperformance",
            name="regression_coeficients",
            field=homebytwo.routes.fields.NumpyArrayField(
                base_field=models.FloatField(), default=array([0.0, 0.0]), size=None
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="activitytype",
            name="flat_parameter",
            field=models.FloatField(default=6.0),
        ),
        migrations.AddField(
            model_name="activitytype",
            name="max_gradient",
            field=models.FloatField(default=100.0),
        ),
        migrations.AddField(
            model_name="activitytype",
            name="max_pace",
            field=models.FloatField(default=40.0),
        ),
        migrations.AddField(
            model_name="activitytype",
            name="min_gradient",
            field=models.FloatField(default=-100.0),
        ),
        migrations.AddField(
            model_name="activitytype",
            name="min_pace",
            field=models.FloatField(default=2.0),
        ),
        migrations.AddField(
            model_name="activitytype",
            name="regression_coeficients",
            field=homebytwo.routes.fields.NumpyArrayField(
                base_field=models.FloatField(), default=array([0.0, 0.0]), size=None
            ),
            preserve_default=False,
        ),
    ]
