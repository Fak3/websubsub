import logging
from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import resolve, Resolver404

from websubsub.models import Subscription
from websubsub.tasks import subscribe

log = logging.getLogger('websubsub')


class Command(BaseCommand):
    # TODO
    help = 'Materialize static subscriptions from settings'

    def handle(self, *args, **kwargs):
        if not settings.WEBSUBS_HUBS:
            print('settings.WEBSUBS_HUBS is empty')

        for hub_url, hub in settings.WEBSUBS_HUBS.items():
            subscriptions = hub.get('subscriptions', [])
            print(f'{len(subscriptions)} static subscriptions for hub {hub_url}')
            for subscription in subscriptions:
                if isinstance(subscription, tuple):
                    raise Exception(
                        'Static subscription was changed from tuple to dict '
                        '{"topic": topic, "callback_urlname": urlname} in Websubsub version 0.7'
                    )
                self.process_subscription(
                    hub_url, 
                    subscription['topic'], 
                    subscription['callback_urlname']
                )
                
        apps.get_app_config('websubsub').check_hub_url_slash_consistency()
        apps.get_app_config('websubsub').check_urls_resolve()


    def process_subscription(self, hub_url, topic, urlname):
        try:
            ssn = Subscription.objects.get(topic=topic, hub_url=hub_url, callback_urlname=urlname)
        except Subscription.DoesNotExist:
            ssn = Subscription.create(topic, urlname, hub_url)
            print(
                f'New static subscription {ssn.pk} with topic {topic} and urlname '
                f'{urlname} is created and scheduled.'
            )
            return

        if ssn.unsubscribe_status is not None:
            # TODO: graceful unsubscribe
            print(f'Static subscription {topic} was explicitly unsubscribed, skipping.')
            return

        subscribe.delay(pk=ssn.pk)
        print(f'Static subscription {ssn.id} with topic {topic} urlname {urlname} scheduled.')

        # TODO: What will be a nice way to heal failed static subscriptions?
