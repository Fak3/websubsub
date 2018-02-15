import re

import responses
from model_mommy.mommy import make
from websubsub.models import Subscription

from .base import BaseTestCase, method_url_body


class VeirfyMalformedTest(BaseTestCase):
    """
    When malformed verification request from hub received, subscription status should be `verifyerror`
    """
    def setUp(self):
        self.callback = '/websubcallback/8b1396c9-9c14-4cd7-9496-99f73742f948'

        # GIVEN Subscription with status 'verifying'
        make(Subscription,
            callback_url=f'http://wss.io{self.callback}',
            topic='news',
            subscribe_status='verifying',
            verifyerror_count=0,
        )

    def test_no_challenge(self):
        # WHEN hub sends subscription verification request without `hub.challenge`
        rr = self.client.get(self.callback, {
            'hub.topic': 'news',
            'hub.lease_seconds': 100,
            'hub.mode': 'subscribe'})

        # THEN response status should be HTTP_400_BAD_REQUEST
        assert rr.status_code == 400

        # AND response body should say that `hub.challenge` is missing
        assert rr.data == 'Missing hub.challenge'

        # AND Subscription status should change to 'verifyerror'
        self.assertEqual(
            list(Subscription.objects.values('topic', 'subscribe_status', 'verifyerror_count')),
            [{
                'topic': 'news',
                'subscribe_status': 'verifyerror',
                'verifyerror_count': 1
            }]
        )

    def test_no_lease(self):
        # WHEN hub sends subscription verification request without `hub.lease_seconds`
        rr = self.client.get(self.callback, {
            'hub.topic': 'news',
            'hub.challenge': '123',
            'hub.mode': 'subscribe'})

        # THEN response status should be HTTP_400_BAD_REQUEST
        assert rr.status_code == 400

        # AND response body should say that `hub.lease_seconds` is missing
        assert rr.data == 'hub.lease_seconds required and must be integer'

        # AND Subscription status should change to 'verifyerror'
        self.assertEqual(
            list(Subscription.objects.values('topic', 'subscribe_status', 'verifyerror_count')),
            [{
                'topic': 'news',
                'subscribe_status': 'verifyerror',
                'verifyerror_count': 1
            }]
        )

    def test_invalid_lease(self):
        # WHEN hub sends subscription verification request with invalid `hub.lease_seconds`
        rr = self.client.get(self.callback, {
            'hub.topic': 'news',
            'hub.lease_seconds': 'QWE!!!!!!!!!',
            'hub.challenge': '123',
            'hub.mode': 'subscribe'})

        # THEN response status should be HTTP_400_BAD_REQUEST
        assert rr.status_code == 400

        # AND response body should say that `hub.lease_seconds` is invalid
        assert rr.data == 'hub.lease_seconds required and must be integer'

        # AND Subscription status should change to 'verifyerror'
        self.assertEqual(
            list(Subscription.objects.values('topic', 'subscribe_status', 'verifyerror_count')),
            [{
                'topic': 'news',
                'subscribe_status': 'verifyerror',
                'verifyerror_count': 1
            }]
        )
