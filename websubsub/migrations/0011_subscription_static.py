# Generated by Django 2.0.13 on 2020-02-16 13:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('websubsub', '0010_subscription_time_last_event_received'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='static',
            field=models.BooleanField(default=False, editable=False),
        ),
    ]
