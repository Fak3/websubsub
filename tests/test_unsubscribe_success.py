import re

import responses
from model_mommy.mommy import make
from websubsub.models import Subscription

from .base import BaseTestCase, method_url_body



class UnubscribeSuccessTest(BaseTestCase):
    """
    Subscription.unsubscribe() should trigger request to hub, and then get marked `verifying`
    """
    def test_unsubscribe_success(self):
        # GIVEN Subscription
        ssn = make(Subscription,
            topic='news',
            hub_url='http://hub.io/',
            callback_url='http://123')

        # AND hub which returns HTTP_202_ACCEPTED
        responses.add('POST', 'http://hub.io', status=202)

        # WHEN Subscription.unsubscribe() is called
        ssn.unsubscribe()

        # THEN one POST request to hub should be sent
        self.assertEqual([method_url_body(x) for x in responses.calls],
            [
                ('POST', 'http://hub.io/', {
                    'hub.mode': ['unsubscribe'],
                    'hub.topic': ['news'],
                    'hub.callback': [ssn.callback_url]
                }),
            ]
        )

        # AND Subscription unsubscribe_status should be to 'verifying'
        self.assertEqual(
            list(Subscription.objects.values('topic', 'unsubscribe_status')),
            [{
                'topic': 'news',
                'unsubscribe_status': 'verifying',
            }]
        )
