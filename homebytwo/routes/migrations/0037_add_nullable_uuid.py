# Generated by Django 2.2.8 on 2019-12-20 18:27

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('routes', '0036_auto_20191220_1520'),
    ]

    operations = [
        migrations.AddField(
            model_name='route',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, null=True),
        ),
    ]
