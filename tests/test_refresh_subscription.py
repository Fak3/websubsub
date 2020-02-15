import re
from datetime import timedelta

import responses
from django.test import override_settings
from model_mommy.mommy import make
from django.utils.timezone import now
from websubsub.models import Subscription
from websubsub.tasks import refresh_subscriptions, retry_failed

from .base import BaseTestCase, method_url_body


class RefreshSubscriptionsTest(BaseTestCase):
    """
    When refresh_subscriptions() task is called, then only verified Subscription with
    lease_expiration_time ending soon should be subscribed again.
    """
    def test_refresh(self):
        # GIVEN hub which returns HTTP_202_ACCEPTED
        responses.add('POST', 'http://hub.io', status=202)

        # AND verified Subscription with expiration time in 3 hours
        torefresh = make(Subscription,
            hub_url='http://hub.io',
            topic='news-topic1', 
            callback_urlname='wscallback',
            lease_expiration_time=now() + timedelta(hours=3),
            subscribe_status='verified'
        )

        # AND explicitly unsubscribed verified Subscription with 
        # expiration time in 3 hours
        unsubscribed = make(Subscription,
            hub_url='http://hub.io',
            topic='news-topic2', 
            callback_urlname='wscallback',
            lease_expiration_time=now() + timedelta(hours=3),
            subscribe_status='verified',
            unsubscribe_status='verified'
        )

        # AND verified Subscription with expiration time in 3 days
        fresh = make(Subscription,
            hub_url='http://hub.io',
            topic='news-topic3', 
            callback_urlname='wscallback',
            lease_expiration_time=now() + timedelta(days=3),
            subscribe_status='verified'
        )

        # AND non-verified Subscription with expiration time in 3 hours
        unverified = make(Subscription,
            hub_url='http://hub.io',
            topic='news-topic4', 
            callback_urlname='wscallback',
            lease_expiration_time=now() + timedelta(hours=3),
            subscribe_status='requesting'
        )

        # WHEN refresh_subscriptions task is called
        refresh_subscriptions.delay()
        #retry_failed.delay()
        
        # THEN no new Subscription should get created
        assert len(Subscription.objects.all()) == 4

        torefresh = Subscription.objects.get(id=torefresh.id)

        # AND one POST request to hub should be sent
        self.assertEqual([method_url_body(x) for x in responses.calls],
            [
                ('POST', 'http://hub.io/', {
                    'hub.mode': ['subscribe'],
                    'hub.topic': [torefresh.topic],
                    'hub.callback': [torefresh.callback_url]
                }),
            ]
        )

        # AND only this subscription_status should be changed from `verified` to `verifying`
        assert dict(Subscription.objects.values_list('id', 'subscribe_status'))  == {
            torefresh.id: 'verifying',  # changed
            unsubscribed.id: 'verified',
            fresh.id: 'verified',
            unverified.id: 'requesting',
        }
