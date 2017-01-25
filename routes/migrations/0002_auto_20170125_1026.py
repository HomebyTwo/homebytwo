# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2017-01-25 09:26
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('routes', '0001_initial'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='route',
            unique_together=set([('user', 'data_source', 'source_id')]),
        ),
    ]
