# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-07-02 19:50
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('routes', '0005_auto_20160702_2149'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='activitytype',
            name='description',
        ),
    ]