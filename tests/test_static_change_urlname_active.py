import re

import responses
from websubsub.models import Subscription
from django.core import management
from django.test import override_settings
from model_mommy.mommy import make

from .base import BaseTestCase, method_url_body


class ActiveStaticSubscriptionChangeUrlnameTest(BaseTestCase):
    """
    When declared static subscription with the existing _active_ subscription 
    in database have same hub and topic, but different urlname, calling 
    `./manage.py websubscribe_static` should update Subscription, urlname, 
    trigger request to hub, and then mark Subscription as `verifying`.
    """
    def test_active(self):
        # GIVEN hub which returns HTTP_202_ACCEPTED
        responses.add('POST', 'http://hub.io', status=202)

        # AND existing _active_ Subscription in the database
        # (Does have callback_url resolved)
        ssn = make(Subscription,
            topic='news',
            hub_url='http://hub.io/',
            callback_urlname='wscallback',
            callback_url='http://123'
        )
        
        # GIVEN settings with static subscription to the same hub and 
        # topic, with different callback urlname
        NEW_WEBSUBS_HUBS = {
            'http://hub.io/': {
                'subscriptions': [{
                    'topic': 'news', 
                    'callback_urlname': 'news_wscallback'  # New urlname
                }]
            }
        }
        with self.settings(WEBSUBS_HUBS = NEW_WEBSUBS_HUBS):
            # WHEN websubscribe_static is called
            management.call_command('websubscribe_static')
            
            # THEN exactly one Subscription should exist in database
            assert len(Subscription.objects.all()) == 1

            ssn = Subscription.objects.first()

            # AND it should get new callback_urlname
            assert ssn.callback_urlname == 'news_wscallback'

            # AND one POST request to hub should be sent
            self.assertEqual([method_url_body(x) for x in responses.calls],
                [
                    ('POST', 'http://hub.io/', {
                        'hub.mode': ['subscribe'],
                        'hub.topic': ['news'],
                        'hub.callback': [ssn.callback_url]
                    }),
                ]
            )

            # AND subscription_status should be `verifying`
            assert ssn.subscribe_status == 'verifying'
