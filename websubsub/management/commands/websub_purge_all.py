from uuid import uuid4
import logging
from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import resolve, reverse, NoReverseMatch

from websubsub.models import Subscription
from websubsub.tasks import subscribe

log = logging.getLogger('websubsub')


class Command(BaseCommand):
    help = 'Delete all subscriptions from database.'

    def handle(self, *args, **kwargs):
        count =  Subscription.objects.count()
        if not count:
            print('No subscriptions in the database.')
            return
        text = f'Are you sure you want to delete {count} subscriptions? (y/N): '
        while True:
            answer = input(text)
            if not answer or answer in ('n','N'):
                return
            if answer in ('y', 'Y'):
                break
        
        Subscription.objects.all().delete()
        print(f'{count} subscriptions was successfully removed from database')
        
