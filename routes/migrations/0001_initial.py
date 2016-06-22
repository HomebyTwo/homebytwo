# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-06-22 08:09
from __future__ import unicode_literals

import django.contrib.gis.db.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Route',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('swissmobility_id', models.BigIntegerField(unique=True)),
                ('totalup', models.FloatField(default=0, verbose_name='Total elevation difference up')),
                ('totaldown', models.FloatField(default=0, verbose_name='Total elevation difference down')),
                ('length', models.FloatField(default=0, verbose_name='Total length of the track in m')),
                ('geom', django.contrib.gis.db.models.fields.LineStringField(srid=21781, verbose_name='line geometry')),
            ],
        ),
    ]