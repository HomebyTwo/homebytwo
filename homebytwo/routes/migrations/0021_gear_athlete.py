# Generated by Django 2.1.11 on 2019-11-05 10:50

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('routes', '0020_auto_20191105_1040'),
    ]

    operations = [
        migrations.AddField(
            model_name='gear',
            name='athlete',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='routes.Athlete'),
            preserve_default=False,
        ),
    ]
