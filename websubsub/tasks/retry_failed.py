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
from . import unsubscribe

logger = logging.getLogger('websubsub.tasks.retry_failed')


@shared_task
def retry_failed():
    """
    This task should be scheduled to launch periodically
    """
    waittime = timedelta(seconds=settings.WEBSUBS_VERIFY_WAIT_TIME)

    #-----------------
    # Subscribe errors
    #-----------------
    verify_timeout = Q(**{
        'subscribe_attempt_time__lt': now() - waittime,
        'subscribe_status': 'verifying',
        # TODO: split this setting for error/timeout counters?
        'verifytimeout_count__lt': settings.WEBSUBS_MAX_VERIFY_RETRIES
    })
    connerror = Q(**{
        'subscribe_status': 'connerror',
        'connerror_count__lt': settings.WEBSUBS_MAX_CONNECT_RETRIES
    })
    huberror = Q(**{
        'subscribe_status': 'huberror',
        'huberror_count__lt': settings.WEBSUBS_MAX_HUB_ERROR_RETRIES
    })
    verifyerror = Q(**{
        'subscribe_status': 'verifyerror',
        # TODO: split this setting for error/timeout counters?
        'verifyerror_count__lt': settings.WEBSUBS_MAX_VERIFY_RETRIES
    })

    max_reached = Subscription.objects.filter(**{
        'subscribe_status': 'connerror',
        'connerror_count__gte': settings.WEBSUBS_MAX_CONNECT_RETRIES,
        'unsubscribe_status__isnull': True
    })
    if max_reached.exists():
        for ssn in max_reached:
            logger.warning(
                f'Subscription {ssn.pk} with topic {ssn.topic} failed to connect '
                f'to the hub at {ssn.hub_url} {settings.WEBSUBS_MAX_CONNECT_RETRIES} '
                f'times. Increase settings.WEBSUBS_MAX_CONNECT_RETRIES to allow more '
                f'attempts. Or reset retry counters with `./manage.py websub_reset_counters`.'
            )
            
    errors = verify_timeout | connerror | huberror | verifyerror

    # Exclude explicitly unsubscribed
    tosubscribe = Subscription.objects.filter(errors & Q(unsubscribe_status__isnull=True))

    logger.debug(f'{tosubscribe.count()} subscriptions to retry subscribe.')
    for ssn in tosubscribe:
        subscribe.delay(pk=ssn.pk)

    #------------------
    # Unubscribe errors
    #------------------
    verify_timeout = Q(**{
        'unsubscribe_attempt_time__lt': now() - waittime,
        'unsubscribe_status': 'verifying',
        # TODO: split this setting for error/timeout counters?
        'verifytimeout_count__lt': settings.WEBSUBS_MAX_VERIFY_RETRIES
    })
    connerror = Q(**{
        'unsubscribe_status': 'connerror',
        'connerror_count__lt': settings.WEBSUBS_MAX_CONNECT_RETRIES
    })
    huberror = Q(**{
        'unsubscribe_status': 'huberror',
        'huberror_count__lt': settings.WEBSUBS_MAX_HUB_ERROR_RETRIES
    })
    verifyerror = Q(**{
        'unsubscribe_status': 'verifyerror',
        # TODO: split this setting for error/timeout counters?
        'verifyerror_count__lt': settings.WEBSUBS_MAX_VERIFY_RETRIES
    })

    errors = verify_timeout | connerror | huberror | verifyerror
    
    tounsubscribe = Subscription.objects.filter(errors)
    logger.debug(f'{tounsubscribe.count()} subscriptions to retry unsubscribe.')
    for ssn in tounsubscribe:
        unsubscribe.delay(pk=ssn.pk)

