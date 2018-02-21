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
        callback = '/websubcallback/8b1396c9-9c14-4cd7-9496-99f73742f948'

        # GIVEN Subscription with unsubscribe status 'verifying'
        make(Subscription,
            callback_url=f'http://wss.io{callback}',
            topic='news',
            unsubscribe_status='verifying'
        )

        # WHEN hub sends valid verification request
        rr = self.client.get(callback, {
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
