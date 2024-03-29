# Generated by Django 4.1.7 on 2023-02-28 17:06

import core.models
from django.conf import settings
import django.core.files.storage
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0014_album_is_private'),
    ]

    operations = [
        migrations.AlterField(
            model_name='album',
            name='cover',
            field=models.ImageField(blank=True, null=True, storage=django.core.files.storage.FileSystemStorage(base_url='/media/', location='G:\\projekts\\2023\\ohooho-master\\app\\media'), upload_to=core.models.user_album_path),
        ),
        migrations.AlterField(
            model_name='album',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='album',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s', to=settings.AUTH_USER_MODEL, verbose_name='user'),
        ),
        migrations.AlterField(
            model_name='author',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='author',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s', to=settings.AUTH_USER_MODEL, verbose_name='user'),
        ),
        migrations.AlterField(
            model_name='classifier',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='domaincontacts',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='domaincontacts',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s', to=settings.AUTH_USER_MODEL, verbose_name='user'),
        ),
        migrations.AlterField(
            model_name='domaindata',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='domaindata',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s', to=settings.AUTH_USER_MODEL, verbose_name='user'),
        ),
        migrations.AlterField(
            model_name='enginecounter',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='enginecounter',
            name='user',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='photo',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='photo',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s', to=settings.AUTH_USER_MODEL, verbose_name='user'),
        ),
        migrations.AlterField(
            model_name='searchresult',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='searchresult',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s', to=settings.AUTH_USER_MODEL, verbose_name='user'),
        ),
        migrations.AlterField(
            model_name='usernps',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='photo',
            field=models.ImageField(storage=django.core.files.storage.FileSystemStorage(base_url='/media/', location='G:\\projekts\\2023\\ohooho-master\\app\\media'), upload_to=core.models.user_profile_path),
        ),
    ]
