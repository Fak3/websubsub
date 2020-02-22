import logging
from datetime import timedelta
from urllib.parse import urljoin
from uuid import uuid4

from celery import shared_task
from django.conf import settings
from django.db.models import Q
from django.urls import reverse
from django.utils.timezone import now
from dumblock import lock_or_exit, lock_wait
from requests import post
from requests.exceptions import ConnectionError
from rest_framework import status

from ..models import Subscription
from . import subscribe

logger = logging.getLogger('websubsub.tasks.refresh_subscriptions')


@shared_task(name='websubsub.tasks.refresh_subscriptions')
def refresh_subscriptions():
    """
    This task should be scheduled to launch periodically
    """
    soon = now() + timedelta(days=1)  # TODO: setting
    _filter = Q(**{
        'lease_expiration_time__lt': soon,
        'subscribe_status': 'verified',
        'unsubscribe_status__isnull': True  # Exclude explicitly unsubscribed
    })
    
    torefresh = Subscription.objects.filter(_filter)
    if torefresh.exists():
        logger.info(f'Refreshing {torefresh.count()} expiring subscriptions.')
    for ssn in torefresh:
        subscribe.delay(pk=ssn.pk)

