# Generated by Django 2.2.11 on 2020-03-15 20:06
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_photo_error_count'),
    ]

    operations = [
        migrations.AddField(
            model_name='enginecounter',
            name='successful',
            field=models.BooleanField(default=True),
        ),
    ]
