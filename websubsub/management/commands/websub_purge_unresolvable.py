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
    help = 'Delete all subscriptions with unresolvable urlname from database.'

    def handle(self, *args, **kwargs):
        unresolvable_pks = set()
        for ssn in Subscription.objects.all():
            try:
                reverse(ssn.callback_urlname, args=[uuid4()])
            except NoReverseMatch:
                unresolvable_pks.add(ssn.pk)
                print(
                    f'Subscription {ssn.pk} with topic {ssn.topic} has unresolvable '
                    f'urlname {ssn.callback_urlname}'
                )
        if not unresolvable_pks:
            print('No unresolvable subscriptions found')
            return
        
        text = f'Are you sure you want to delete {len(unresolvable_pks)} subscriptions? (y/N): '
        while True:
            answer = input(text)
            if not answer or answer in ('n','N'):
                return
            if answer in ('y', 'Y'):
                break
        
        Subscription.objects.filter(pk__in=unresolvable_pks).delete()
        print(f'{len(unresolvable_pks)} subscriptions was successfully removed from database')
        
