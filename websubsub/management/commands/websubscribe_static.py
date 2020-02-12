
from django.conf import settings
from django.core.management.base import BaseCommand

from websubsub.models import Subscription
from websubsub.tasks import subscribe


class Command(BaseCommand):
    # TODO
    help = 'Materialize static subscriptions from settings'

    def handle(self, *args, **kwargs):
        if not settings.WEBSUBS_HUBS:
            print('settings.WEBSUBS_HUBS is empty')

        for hub_url, hub in settings.WEBSUBS_HUBS.items():
            subscriptions = hub.get('subscriptions', [])
            print(f'{len(subscriptions)} static subscriptions for hub {hub_url}')
            for topic, urlname in subscriptions:
                self.process_subscription(hub_url, topic, urlname)


    def process_subscription(self, hub_url, topic, urlname):
        try:
            ssn = Subscription.objects.get(topic=topic, hub_url=hub_url)
        except Subscription.DoesNotExist:
            Subscription.create(topic, urlname, hub_url)
            print(f'Static subscription {topic} is created and scheduled.')
            return

        if ssn.unsubscribe_status is not None:
            print(f'Static subscription {topic} was explicitly unsubscribed, skipping.')
            return

        if ssn.callback_urlname != urlname:
            if not ssn.callback_url:
                # We did not subscribe with hub yet.
                print(f'Scheduling static subscription {topic}.')
                ssn.update(callback_urlname=urlname)
                subscribe.delay(pk=ssn.pk)
                return

            # TODO We should probably check all subscription callback_urls in the
            # same way on start.
            try:
                cur_resolved = resolve(ssn.callback_url).url_name
            except Resolver404:
                # Callback url does not resolve anymore. We can't gracefully tell hub
                # to unsubscribe.
                logger.error(
                    f'Static subscription {ssn.pk} with topic "{topic}" has unresolvabe '
                    f'callback url! Resubscribing with new urlname "{urlname}".')
                ssn.update(callback_urlname=urlname)
                subscribe.delay(pk=ssn.pk)
                return

            if cur_resolved == urlname:
                # Urlname was changed, while url pattern remain the same. It is fine
                # to just change Subscription.callback_urlname
                print(f'Static subscription {ssn.pk}: changing urlname to {urlname}')
                ssn.update(callback_urlname=urlname)
            else:
                # Urlname and pattern was changed, we should unsubscribe with hub,
                # and then resubscribe
                # TODO
                logger.warning(
                    f'Static subscription {topic} is subscribed to different callback'
                    f' urlname, than specified in settings! Will resubscribe.')
                ssn.callback_urlname = urlname
                ssn.save()
                subscribe.delay(pk=ssn.pk)
                return

        if ssn.subscribe_status not in ['verifying', 'verified']:
            # Let's schedule it
            print(f'Scheduling static subsctiption {topic}.')
            subscribe.delay(pk=ssn.pk)
            return

        # TODO: What will be a nice way to heal failed static subscriptions?
        print(f'Static subsctiption {topic} already exists, skipping.')
