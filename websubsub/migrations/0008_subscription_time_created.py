# Generated by Django 2.0.13 on 2020-02-15 14:00

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('websubsub', '0007_auto_20200215_0013'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='time_created',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]