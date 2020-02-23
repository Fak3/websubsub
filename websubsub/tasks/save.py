import json
import logging
from collections import defaultdict
from datetime import timedelta
from urllib.parse import urljoin
from uuid import uuid4

from celery import shared_task
from django.conf import settings
from django.db.models import Q, Count
from django.urls import reverse
from django.utils.timezone import now
from dumblock import lock_or_exit, lock_wait
from requests import post
from requests.exceptions import ConnectionError
from rest_framework import status

from ..models import Subscription
#from . import subscribe

logger = logging.getLogger('websubsub.tasks.save')


@shared_task(name='websubsub.tasks.save')
@lock_wait('websubsub_{pk}')
def save(*, pk, **kwargs):
    """
    Update Subscription in the database with new values.
    """
    try:
        ssn = Subscription.objects.get(pk=pk)
    except Subscription.DoesNotExist:
        logger.error(
            f'Received update of subscription {pk} with values {kwargs}, but this '
            f'subscription does not exist.'
        )
        return
    
    if kwargs.get('subscribe_status') == 'verified' and not ssn.subscribe_status == 'verifying':
        logger.warning(
            f'Updating subscription {pk} subscribe_status to "verified", but its current status'
            f'is not "verifying", it is {ssn.subscribe_status}.'
        )
        
    Subscription.objects.filter(pk=pk).update(**kwargs)
    if kwargs.get('subscribe_status') == 'verified':
        logger.info(f'Subscription {pk} verified.')
    else:
        logger.info(f'Subscription {pk} updated with {kwargs}.')

    if kwargs.get('subscribe_status') == 'verified' and settings.DEBUG:
        # Print statistics by subscribe_status
        by_status = defaultdict(list)
        for ssn in Subscription.objects.filter(static=True):
            by_status[ssn.subscribe_status].append({
                'id': str(ssn.id),
                'hub': ssn.hub_url,
                'topic': ssn.topic,
                'callback_urlname': ssn.callback_urlname
            })
        logger.debug('Static subscriptions by status:\n' + json.dumps(by_status, indent=2))
        
        dynamic = Subscription.objects.filter(static=False)
        if dynamic.exists():
            # Awkward django way to do SELECT subscribe_status, COUNT(subscribe_status) AS "total" FROM "websubsub_subscription" GROUP BY subscribe_status
            count = dynamic.values_list('subscribe_status').annotate(total=Count('subscribe_status'))
            logger.debug(f'Non-static subscriptions by status: {dict(count)}')
        else:
            logger.debug('Non-static: 0')
        
