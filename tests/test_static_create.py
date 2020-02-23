import re

import responses
from websubsub.models import Subscription
from django.core import management
from django.test import override_settings

from .base import BaseTestCase, method_url_body


# GIVEN static subscription
@override_settings(
    WEBSUBSUB_HUBS = {
        'http://hub.io': {
            'subscriptions': [{
                'topic': 'news', 
                'callback_urlname': 'wscallback'  # New urlname
            }]
        }
})
class StaticSubscriptionCreateTest(BaseTestCase):
    """
    calling websub_static_subscribe should create Subscription, trigger request to hub, 
    and then mark Subscription as `verifying`.
    """
    def test_subscribe_success(self):
        # GIVEN hub which returns HTTP_202_ACCEPTED
        responses.add('POST', 'http://hub.io', status=202)

        # WHEN websub_static_subscribe is called
        management.call_command('websub_static_subscribe')
        
        # THEN exactly one Subscription should get created
        assert len(Subscription.objects.all()) == 1

        ssn = Subscription.objects.first()

        # AND it should get new callback_url generated
        assert re.match('http://wss.io/websubcallback/*.', ssn.callback_url)

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
