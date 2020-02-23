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

logger = logging.getLogger('websubsub.tasks.unsubscribe')


@shared_task(name='websubsub.tasks.unsubscribe', retries=10)
@lock_wait('websubsub_{pk}')
def unsubscribe(*, pk):
    ssn = Subscription.objects.get(pk=pk)

    if ssn.unsubscribe_status is None:
        logger.warning(f'Subscription {ssn.pk} was explicitly resubscribed, skipping.')
        return

    waittime = timedelta(seconds=settings.WEBSUBSUB_VERIFY_WAIT_TIME)
    if ssn.unsubscribe_status == 'verifying' \
       and now() < ssn.unsubscribe_attempt_time + waittime:
        logger.warning(
            f'Subscription {ssn.pk} was attempted to unsubscribe recently and'
            f'waiting for verification. Skipping.'
        )
        return

    data = {
        'hub.mode': 'unsubscribe',
        'hub.topic': ssn.topic,
        'hub.callback': ssn.callback_url,
    }
    try:
        # TODO: timeout setting
        rr = post(ssn.hub_url, data, timeout=10)
    except Exception as e:
        ssn.connerror_count += 1
        ssn.unsubscribe_status = 'connerror'
        ssn.save()
        if isinstance(e, ConnectionError):
            logger.error(str(e))
        else:
            logger.exception(e)
        left = max(0, settings.WEBSUBSUB_MAX_CONNECT_RETRIES - ssn.connerror_count)
        logger.error(f'While unsubscribing {ssn.pk} failed to connect to hub. Retries left: {left}')
        return
    else:
        logger.debug(f'Subscription {ssn.pk}, got hub response')
    finally:
        ssn.unsubscribe_attempt_time = now()
        ssn.save()

    # If the hub URL supports WebSub and is able to handle the subscription or unsubscription
    # request, it MUST respond to a subscription request with an HTTP 202 "Accepted" response
    # to indicate that the request was received and will now be verified and validated by the
    # hub.
    # If a hub finds any errors in the subscription request, an appropriate HTTP error response
    # code (4xx or 5xx) MUST be returned. In the event of an error, hubs SHOULD return a
    # description of the error in the response body as plain text, used to assist the client
    # developer in understanding the error. This is not meant to be shown to the end user.
    if rr.status_code != status.HTTP_202_ACCEPTED:
        # TODO: handle specific response codes accordingly
        ssn.unsubscribe_status = 'huberror'
        ssn.huberror_count += 1
        ssn.save()
        left = max(0, settings.WEBSUBSUB_MAX_HUB_ERROR_RETRIES - ssn.huberror_count)
        logger.error(f'Subscription {ssn.pk} got hub error {rr.status_code}. Retries left: {left}')
        return

    ssn.unsubscribe_status = 'verifying'
    ssn.save()

