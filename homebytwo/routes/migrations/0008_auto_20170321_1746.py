# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-03-21 16:46
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('routes', '0007_auto_20170320_1245'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='routeplace',
            options={'ordering': ('line_location',)},
        ),
    ]
