# Generated by Django 2.2.11 on 2020-03-14 10:11
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_album_title'),
    ]

    operations = [
        migrations.RenameField(
            model_name='enginecounter',
            old_name='count',
            new_name='result_count',
        ),
        migrations.AddField(
            model_name='enginecounter',
            name='search_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='photo',
            name='search_count',
            field=models.IntegerField(default=0),
        ),
    ]
