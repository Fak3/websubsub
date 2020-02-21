import logging
from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import resolve, Resolver404

from websubsub.models import Subscription
from websubsub.tasks import subscribe

log = logging.getLogger('websubsub')


class Command(BaseCommand):
    # TODO
    help = 'Reset retry counters for all subscriptions in database.'

    def handle(self, *args, **kwargs):

        Subscription.objects.update(
            connerror_count = 0,
            huberror_count = 0,
            verifytimeout_count = 0,
            verifyerror_count = 0,
            subscribe_attempt_time = None,
            unsubscribe_attempt_time = None
        )
        print(
            f'{Subscription.objects.count()} subscriptions retry counters now got'
            ' reset to\n'
            '  connerror_count = 0\n'
            '  huberror_count = 0\n'
            '  verifytimeout_count = 0\n'
            '  verifyerror_count = 0\n'
            '  subscribe_attempt_time = None\n'
            '  unsubscribe_attempt_time = None'
        )
