# -*- coding: utf-8 -*-
# Generated by Django 1.11.9 on 2018-02-10 13:54
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hub_url', models.TextField()),
                ('topic', models.TextField()),
                ('callback_urlname', models.CharField(max_length=200)),
                ('callback_url', models.TextField(null=True)),
                ('lease_expiration_time', models.DateTimeField(blank=True, null=True)),
                ('subscribe_status', models.CharField(choices=[('requesting', 'scheduled to be requested asap'), ('connerror', 'connection error'), ('huberror', 'hub returned error'), ('verifying', 'waiting for hub verification request'), ('verifyerror', 'verification failure'), ('verified', 'verified'), ('denied', 'hub denied subscription')], default='requesting', max_length=20)),
                ('unsubscribe_status', models.CharField(blank=True, choices=[('requesting', 'scheduled to be requested asap'), ('connerror', 'connection error'), ('huberror', 'hub returned error'), ('verifying', 'waiting for hub verification request'), ('verifyerror', 'verification failure'), ('verified', 'verified')], max_length=20, null=True)),
                ('connerror_count', models.IntegerField(default=0)),
                ('huberror_count', models.IntegerField(default=0)),
                ('verifytimeout_count', models.IntegerField(default=0)),
                ('verifyerror_count', models.IntegerField(default=0)),
                ('subscribe_attempt_time', models.DateTimeField(blank=True, null=True)),
                ('unsubscribe_attempt_time', models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='subscription',
            unique_together=set([('hub_url', 'topic')]),
        ),
    ]
