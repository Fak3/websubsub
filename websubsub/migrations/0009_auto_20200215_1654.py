# Generated by Django 2.0.13 on 2020-02-15 14:54

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('websubsub', '0008_subscription_time_created'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='subscription',
            unique_together={('hub_url', 'topic', 'callback_urlname')},
        ),
    ]
