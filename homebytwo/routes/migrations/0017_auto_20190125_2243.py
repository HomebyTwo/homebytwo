# Generated by Django 2.1.5 on 2019-01-25 21:43

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('routes', '0016_auto_20180831_1540'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='RoutePlace',
            new_name='Checkpoint',
        ),
    ]
