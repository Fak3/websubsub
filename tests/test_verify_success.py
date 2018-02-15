import re

import responses
from model_mommy.mommy import make
from websubsub.models import Subscription

from .base import BaseTestCase, method_url_body


class VeirfySuccessTest(BaseTestCase):
    """
    When valid verification request from hub received, subscription should be marked 'verified'.
    """
    def test_success(self):
        callback = '/websubcallback/8b1396c9-9c14-4cd7-9496-99f73742f948'

        # GIVEN Subscription with status 'verifying'
        make(Subscription,
            callback_url=f'http://wss.io{callback}',
            topic='news',
            subscribe_status='verifying'
        )

        # WHEN hub sends valid subscription verification request
        rr = self.client.get(callback, {
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
