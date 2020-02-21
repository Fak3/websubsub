import logging
from datetime import timedelta
from urllib.parse import urljoin
from uuid import uuid4

from celery import shared_task
from django.conf import settings
from django.db.models import Q
from django.urls import reverse, NoReverseMatch
from django.utils.timezone import now
from dumblock import lock_or_exit, lock_wait
from requests import post
from requests.exceptions import ConnectionError
from rest_framework import status

from ..models import Subscription

logger = logging.getLogger('websubsub.tasks.subscribe')

def _declared_static_subscriptions():
    for hub_url, hub in settings.WEBSUBSUB_HUBS.items():
        for ssn in hub.get('subscriptions', []):
            yield (hub_url, ssn['callback_urlname'], ssn['topic'])

@shared_task
@lock_or_exit('websubsub_{pk}')
def subscribe(*, pk):
    ssn = Subscription.objects.get(pk=pk)

    if ssn.unsubscribe_status is not None:
        logger.warning(f'Subscription {ssn.pk} was explicitly unsubscribed, skipping.')
        return

    waittime = timedelta(seconds=settings.WEBSUBSUB_VERIFY_WAIT_TIME)
    if ssn.subscribe_status == 'verifying' \
       and now() < ssn.subscribe_attempt_time + waittime:
        logger.info(
            f'Subscription {ssn.pk} was attempted to subscribe recently and '
            f'waiting for hub to send us confirmation request. Skipping.'
        )
        return

    try:
        path = reverse(ssn.callback_urlname, args=[ssn.id])
    except NoReverseMatch as e:
        if ssn.static:
            current = list(_declared_static_subscriptions())
            if (ssn.hub_url, ssn.callback_urlname, ssn.topic) in current:
                msg = (
                    f'Failed to subscribe static subscription {ssn.pk}: unresolvable '
                    f'callback_urlname "{ssn.callback_urlname}". You can try to resolve '
                    f'this using one of the following:\n'
                    ' * Run `./manage.py websub_handle_url_changes` to fix urlnames in your '
                    'database.\n'
                    ' * Run `./manage.py websub_static_subscribe` to \n'
                    ' * Run `./manage.py websub_purge_unresolvalbe` to delete all unresolvable '
                    'subscriptions from database.'
                )
            else:
                msg = (
                    f'Failed to resolve callback_urlname "{ssn.callback_urlname}". It looks '
                    f'like you have changed static subscriptions: orphan static subscription '
                    f'{ssn.pk} in the database no longer exists in your settings. You can try '
                    f'to resolve this using one of the following:\n'
                    ' * Run `./manage.py websub_handle_url_changes` to fix urlnames in your '
                    'database.\n'
                    ' * Run `./manage.py websub_static_subscribe --purge-orphans` to delete old '
                    'static subscriptions from your database.\n'
                    ' * Run `./manage.py websub_purge_unresolvalbe` to delete all unresolvable '
                    'subscriptions from database.'
                )
        else:
            msg = (
                f'Failed to subscribe subscription {ssn.pk}: unresolvable callback_urlname '
                f'"{ssn.callback_urlname}". You can try to resolve this using one of the '
                'following:\n'
                ' * Run `./manage.py websub_handle_url_changes` to fix urlnames in your '
                'database\n'
                ' * Run `./manage.py websub_purge_unresolvalbe` to delete all unresolvable '
                'subscriptions from database.'
            )
        raise Exception(msg) from e
    
    fullurl = urljoin(settings.WEBSUBSUB_OWN_ROOTURL, path)
    if ssn.callback_url \
       and not ssn.callback_url == fullurl \
       and not settings.WEBSUBSUB_AUTOFIX_URLS:
        logger.error(
            f'Will not change subscription {ssn.pk} callback url to {fullurl} . '
            'Please set settings.WEBSUBSUB_AUTOFIX_URLS to True or Run '
            '`manage.py websub_handle_url_changes`.'
        )
        return
            
    if not ssn.callback_url == fullurl:
        logger.debug(f'Subscription {ssn.pk} new callback url: {fullurl}')
    
    ssn.callback_url = fullurl
    
    data = {
        'hub.mode': 'subscribe',
        'hub.topic': ssn.topic,
        'hub.callback': ssn.callback_url,
    }
    try:
        # TODO: timeout setting
        response = post(ssn.hub_url, data, timeout=10)
    except Exception as e:
        ssn.connerror_count += 1
        ssn.subscribe_status = 'connerror'
        ssn.save()
        if isinstance(e, ConnectionError):
            logger.error(str(e))
        else:
            logger.exception(e)
        left = max(0, settings.WEBSUBSUB_MAX_CONNECT_RETRIES - ssn.connerror_count)
        logger.error(f'Subscription {ssn.pk} failed to connect to hub '
                     f'{ssn.hub_url}. Retries left: {left}')
        return
    else:
        if settings.DEBUG:
            logger.info(f'Subscription {ssn.pk} with topic {ssn.topic}, urlname {ssn.callback_urlname}, got hub response {response}')
        else:
            logger.info(f'Subscription {ssn.pk}, got hub response')
    finally:
        ssn.subscribe_attempt_time = now()
        ssn.save()

    # If the hub URL supports WebSub and is able to handle the subscription or unsubscription
    # request, it MUST respond to a subscription request with an HTTP 202 "Accepted" response
    # to indicate that the request was received and will now be verified and validated by the
    # hub.
    # If a hub finds any errors in the subscription request, an appropriate HTTP error response
    # code (4xx or 5xx) MUST be returned. In the event of an error, hubs SHOULD return a
    # description of the error in the response body as plain text, used to assist the client
    # developer in understanding the error. This is not meant to be shown to the end user.
    if response.status_code != status.HTTP_202_ACCEPTED:
        # TODO: handle specific response codes accordingly
        ssn.subscribe_status = 'huberror'
        ssn.huberror_count += 1
        ssn.save()
        left = max(0, settings.WEBSUBSUB_MAX_HUB_ERROR_RETRIES - ssn.huberror_count)
        logger.error(f'Subscription {ssn.pk} got hub error {response.status_code}. Retries left: {left}')
        return

    ssn.subscribe_status = 'verifying'
    ssn.save()

