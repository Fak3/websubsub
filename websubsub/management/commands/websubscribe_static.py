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
            
        current = []
        for hub_url, hub in settings.WEBSUBS_HUBS.items():
            subscriptions = hub.get('subscriptions', [])
            print(f'Found {len(subscriptions)} static subscriptions for hub {hub_url} in settings\n')
            for subscription in subscriptions:
                if isinstance(subscription, tuple):
                    raise Exception(
                        'Static subscription was changed from tuple to dict '
                        '{"topic": topic, "callback_urlname": urlname} in Websubsub version 0.7'
                    )
                ssn = self.process_subscription(
                    hub_url, 
                    subscription['topic'], 
                    subscription['callback_urlname']
                )
                current.append(ssn.pk)
                
        for ssn in Subscription.objects.filter(static=False).exclude(pk__in=current):
            print(
                f'\nFound old static subscription {ssn.pk} in database: \n'
                f'  hub: {ssn.hub_url}\n'
                f'  topic: {ssn.topic}\n'
                f'  callback_urlname: {ssn.callback_urlname}'
            )
            while True:
                answer = input(f'Do you want to delete it? (y/N): ')
                if not answer or answer in ('n','N'):
                    break
                if answer in ('y', 'Y'):
                    ssn.delete()
                    print(f'Subscription {ssn.pk} deleted.')
                    break
        apps.get_app_config('websubsub').check_hub_url_slash_consistency()
        apps.get_app_config('websubsub').check_urls_resolve()


    def process_subscription(self, hub_url, topic, urlname):
        try:
            ssn = Subscription.objects.get(topic=topic, hub_url=hub_url, callback_urlname=urlname)
        except Subscription.DoesNotExist:
            ssn = Subscription.create(topic, urlname, hub_url, static=True)
            print(
                f'New static subscription {ssn.pk} with \n'
                f'  hub: {hub_url} \n'
                f'  topic: {topic} \n'
                f'  callback_urlname: {urlname}\n'
                f'is created and scheduled.\n'
            )
            return ssn
        
        ssn.update(static=True)

        if ssn.unsubscribe_status is not None:
            # TODO: graceful unsubscribe
            print(f'Static subscription {topic} was explicitly unsubscribed, skipping.')
            return ssn

        subscribe.delay(pk=ssn.pk)
        print(
            f'Static subscription {ssn.pk} with \n'
            f'  hub: {hub_url} \n'
            f'  topic: {topic} \n'
            f'  callback_urlname: {urlname}\n'
            f'is scheduled.\n'
        )

        return ssn
        # TODO: What will be a nice way to heal failed static subscriptions?
