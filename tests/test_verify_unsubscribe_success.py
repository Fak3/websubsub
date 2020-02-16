import re

import responses
from model_mommy.mommy import make
from websubsub.models import Subscription

from .base import BaseTestCase, method_url_body


class VeirfyUnsubscribeSuccessTest(BaseTestCase):
    """
    When valid verification request from hub received, subscription should be marked 'verified'.
    """
    def test_success(self):
        # GIVEN Subscription with unsubscribe status 'verifying'
        ssn = make(Subscription,
            callback_urlname='wscallback',
            topic='news',
            unsubscribe_status='verifying'
        )

        # WHEN hub sends valid verification request
        rr = self.client.get(ssn.reverse_fullurl(), {
            'hub.topic': 'news',
            'hub.challenge': '123',
            'hub.mode': 'unsubscribe'})

        # THEN response status should be HTTP_200_OK
        assert rr.status_code == 200

        # AND response body should echo the provided `hub.challenge`
        assert rr.content == b'123'

        # AND Subscription unsubscribe_status should change to 'verified'
        self.assertEqual(
            list(Subscription.objects.values('topic', 'unsubscribe_status', 'verifyerror_count')),
            [{
                'topic': 'news',
                'unsubscribe_status': 'verified',
                'verifyerror_count': 0
            }]
        )
