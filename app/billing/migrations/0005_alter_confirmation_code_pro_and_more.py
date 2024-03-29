# Generated by Django 4.1.7 on 2023-02-28 17:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0004_subscriptionhistory_search_count'),
    ]

    operations = [
        migrations.AlterField(
            model_name='confirmation',
            name='code_pro',
            field=models.BooleanField(blank=True, default=False, null=True),
        ),
        migrations.AlterField(
            model_name='confirmation',
            name='unaccepted',
            field=models.BooleanField(blank=True, default=False, null=True),
        ),
        migrations.AlterField(
            model_name='invoice',
            name='items',
            field=models.JSONField(default=dict),
        ),
    ]
