# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2016-12-15 08:22
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('routes', '0014_auto_20161214_2320'),
    ]

    operations = [
        migrations.AlterField(
            model_name='place',
            name='source_id',
            field=models.CharField(max_length=50, verbose_name='Place ID at the data source'),
        ),
    ]
