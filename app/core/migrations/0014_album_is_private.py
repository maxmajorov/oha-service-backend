# Generated by Django 2.2.11 on 2020-04-27 18:35
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_author_is_private'),
    ]

    operations = [
        migrations.AddField(
            model_name='album',
            name='is_private',
            field=models.BooleanField(default=False),
        ),
    ]
