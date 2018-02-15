import re

import responses
from websubsub.models import Subscription

from .base import BaseTestCase, method_url_body



class SubscribeSuccessTest(BaseTestCase):
    """
    Subscription.create() should trigger request to hub, and then get marked `verifying`
    """
    def test_subscribe_success(self):
        # GIVEN hub which returns HTTP_202_ACCEPTED
        responses.add('POST', 'http://hub.io', status=202)

        # WHEN Subscription.create() called
        Subscription.create('news', urlname='wscallback')

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
