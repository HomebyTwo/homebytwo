# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-06-22 08:42
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('places', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='place',
            name='description',
            field=models.TextField(default='', verbose_name='Text description of the Place'),
            preserve_default=False,
        ),
    ]
