# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-06-22 08:08
from __future__ import unicode_literals

import django.contrib.gis.db.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Place',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('place_type', models.CharField(max_length=50)),
                ('altitude', models.FloatField()),
                ('name', models.CharField(max_length=250)),
                ('geom', django.contrib.gis.db.models.fields.MultiPointField(srid=21781)),
            ],
        ),
    ]