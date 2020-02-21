import re

import responses
from websubsub.models import Subscription
from django.core import management
from django.test import override_settings
from model_mommy.mommy import make
from unittest.mock import ANY

from .base import BaseTestCase, method_url_body


@override_settings(WEBSUBSUB_AUTOFIX_URLS=True)
class StaticSubscriptionExistingTest(BaseTestCase):
    """
    When declared static subscription already exists in database, calling 
    `./manage.py websub_static_subscribe` should trigger request to hub, and 
    then mark Subscription as `verifying`.
    """
    def test_static_existing(self):
        # GIVEN hub which returns HTTP_202_ACCEPTED
        responses.add('POST', 'http://hub.io', status=202)

        # AND existing Subscription in the database
        ssn = make(Subscription,
            topic='news',
            hub_url='http://hub.io/',
            callback_urlname='wscallback',
            callback_url='http://123'
        )
        
        # GIVEN settings with static subscription to the same hub,
        # topic, and urlname
        NEW_WEBSUBSUB_HUBS = {
            'http://hub.io/': {
                'subscriptions': [{
                    'topic': 'news', 
                    'callback_urlname': 'wscallback'
                }]
            }
        }
        with self.settings(WEBSUBSUB_HUBS = NEW_WEBSUBSUB_HUBS):
            # WHEN websub_static_subscribe is called
            management.call_command('websub_static_subscribe')
            
            # THEN exactly one Subscription should exist in database
            assert len(Subscription.objects.all()) == 1

            # AND it should get new callback_urlname
            assert list(Subscription.objects.values()) == [{
                'id': ssn.pk,
                'static': True,
                'callback_url': f'http://wss.io/websubcallback/{ssn.pk}',
                'callback_urlname': 'wscallback',
                'connerror_count': 0,
                'hub_url': 'http://hub.io/',
                'huberror_count': 0,
                'lease_expiration_time': None,
                'subscribe_attempt_time': ANY,
                'subscribe_status': 'verifying',
                'time_created': ANY,
                'topic': 'news',
                'unsubscribe_attempt_time': None,
                'unsubscribe_status': None,
                'verifyerror_count': 0,
                'verifytimeout_count': 0,
                'time_last_event_received': ANY
            }]

            # AND one POST request to hub should be sent
            self.assertEqual([method_url_body(x) for x in responses.calls],
                [
                    ('POST', 'http://hub.io/', {
                        'hub.mode': ['subscribe'],
                        'hub.topic': ['news'],
                        'hub.callback': [f'http://wss.io/websubcallback/{ssn.pk}']
                    }),
                ]
            )
