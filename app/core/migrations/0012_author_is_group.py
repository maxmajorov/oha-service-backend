# Generated by Django 2.2.11 on 2020-04-26 17:34
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_auto_20200419_1322'),
    ]

    operations = [
        migrations.AddField(
            model_name='author',
            name='is_group',
            field=models.BooleanField(default=False),
        ),
    ]