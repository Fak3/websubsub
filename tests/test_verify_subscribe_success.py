import re

import responses
from model_mommy.mommy import make
from websubsub.models import Subscription

from .base import BaseTestCase, method_url_body


class VeirfySubscribeSuccessTest(BaseTestCase):
    """
    When valid verification request from hub received, subscription should be marked 'verified'.
    """
    def test_success(self):
        # GIVEN Subscription with status 'verifying'
        ssn = make(Subscription,
            callback_urlname='wscallback',
            topic='news',
            subscribe_status='verifying'
        )

        # WHEN hub sends valid subscription verification request
        rr = self.client.get(ssn.reverse_fullurl(), {
            'hub.topic': 'news',
            'hub.challenge': '123',
            'hub.lease_seconds': 100,
            'hub.mode': 'subscribe'})

        # THEN response status should be HTTP_200_OK
        assert rr.status_code == 200

        # AND response body should echo the provided `hub.challenge`
        assert rr.content == b'123'

        # AND Subscription status should change to 'verified'
        self.assertEqual(
            list(Subscription.objects.values('topic', 'subscribe_status', 'verifyerror_count')),
            [{
                'topic': 'news',
                'subscribe_status': 'verified',
                'verifyerror_count': 0
            }]
        )
