# Generated by Django 2.2.11 on 2020-03-14 12:13
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0002_auto_20200104_1643'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscriptionhistory',
            name='fix_parameter',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]