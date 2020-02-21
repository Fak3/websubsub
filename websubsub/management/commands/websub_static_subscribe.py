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

    def add_arguments(self, parser):
        parser.add_argument(
            '--purge-orphans',
            action='store_true',
            help='delete old static subscriptions from database',
        )
        parser.add_argument(
            '-y', '--yes',
            action='store_true',
            help='answer yes to all',
        )
        parser.add_argument(
            '--reset-counters',
            action='store_true',
            help='reset retry counters',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='send new subscription request to hub even if already subscribed',
        )
        
    def handle(self, *args, **kwargs):
        if not settings.WEBSUBSUB_HUBS:
            print('settings.WEBSUBSUB_HUBS is empty')
            
        current = []
        for hub_url, hub in settings.WEBSUBSUB_HUBS.items():
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
                    subscription['callback_urlname'],
                    **kwargs
                )
                current.append(ssn.pk)
                
        if kwargs['purge_orphans']:
            self.purge_orphans(current, **kwargs)
            
        apps.get_app_config('websubsub').check_hub_url_slash_consistency()
        apps.get_app_config('websubsub').check_urls_resolve()
    
    
    def process_subscription(self, hub, topic, urlname, **kwargs):
        try:
            ssn = Subscription.objects.get(topic=topic, hub_url=hub, callback_urlname=urlname)
        except Subscription.DoesNotExist:
            ssn = Subscription.create(topic, urlname, hub, static=True)
            created = True
        else:
            created = False
            
        try:
            newurl = ssn.reverse_fullurl()
        except NoReverseMatch:
            print(
                f'Error: static subscription {ssn.pk} with topic "{ssn.topic}" has unresolvable '
                f'callback_urlname "{ssn.callback_urlname}". Change callback_urlname in your '
                f'settings.'
            )
            return ssn
        
        if created:
            # New subscription, nothing more to do.
            print(
                f'New static subscription {ssn.pk} with \n'
                f'  hub: {hub} \n'
                f'  topic: {topic} \n'
                f'  callback_urlname: {urlname}\n'
                f'is created and scheduled.\n'
            )
            subscribe.delay(pk=ssn.pk)
            return ssn
        
        # Mark subscription as static, even if it was previously created dynamically.
        if not ssn.static:
            ssn.update(static=True)
            print(
                f'Subscription {ssn.pk} with topic "{ssn.topic}" and callback_urlname '
                f'{ssn.callback_urlname} was previously created dynamically at run-time, '
                f'changing it to be static.'
            )

        if kwargs['reset_counters']:
            print(f'Resetting subscription {ssn.pk} retry counters to zero.')
            ssn.update(
                connerror_count = 0,
                huberror_count = 0,
                verifytimeout_count = 0,
                verifyerror_count = 0,
                subscribe_attempt_time = None,
                unsubscribe_attempt_time = None
            )
            
        if ssn.unsubscribe_status is not None:
            if kwargs['force']:
                print(
                    f'Static subscription {ssn.pk} with topic "{topic}" was previously '
                    f'explicitly unsubscribed, forcing resubscribe.'
                )
                ssn.update(unsubscribe_status=None, subscribe_status='requesting')
                if not kwargs['reset_counters']:
                    # If --reset-counters is false, we have not reset counters above, so 
                    # we must do it now to ensure force resubscribe.
                    print(f'Resetting subscription {ssn.pk} retry counters to zero.')
                    ssn.update(
                        connerror_count = 0,
                        huberror_count = 0,
                        verifytimeout_count = 0,
                        verifyerror_count = 0,
                        subscribe_attempt_time = None,
                        unsubscribe_attempt_time = None
                    )
                subscribe.delay(pk=ssn.pk)
            else:
                # TODO: graceful unsubscribe
                print(
                    f'Static subscription {ssn.pk} with topic "{topic}" was previously '
                    f'explicitly unsubscribed, skipping. Provide --force flag if you want '
                    'to force resubscribe.'
                )
            return ssn

        if not ssn.callback_url == newurl:
            print(
                f'It looks like you have changed urls recently. Static subscription '
                f'{ssn.pk} with topic "{ssn.topic}" and urlname {ssn.callback_urlname} '
                f'previously was attempted to subscribe with callback_url '
                f'{ssn.callback_url}, but now this urlname resolves to {newurl}. '
                f'Scheduling to resubscribe with new callback_url.'
            )
            subscribe.delay(pk=ssn.pk)
            return ssn
        
        if ssn.subscribe_status == 'verified' and not kwargs['force']:
            print(
                f'Static subscription {ssn.pk} with topic "{topic}" is already subscribed. '
                f'Provide --force flag if you want to force resubscribe.'
            )
            return ssn
            
        subscribe.delay(pk=ssn.pk)
        print(
            f'Static subscription {ssn.pk} with \n'
            f'  hub: {hub} \n'
            f'  topic: {topic} \n'
            f'  callback_urlname: {urlname}\n'
            f'is scheduled.\n'
        )

        return ssn
    

    def purge_orphans(self, current, **kwargs):
        # Delete old static subscriptions from database.
        for ssn in Subscription.objects.filter(static=True).exclude(pk__in=current):
            print(
                f'\nFound orphan static subscription {ssn.pk} in database: \n'
                f'  hub: {ssn.hub_url}\n'
                f'  topic: {ssn.topic}\n'
                f'  callback_urlname: {ssn.callback_urlname}'
            )
            
            if kwargs['yes']:
                ssn.delete()
                print(f'Subscription {ssn.pk} deleted.')
                continue
            
            while True:
                answer = input(f'Do you want to delete it? (y/N): ')
                if not answer or answer in ('n','N'):
                    break
                if answer in ('y', 'Y'):
                    ssn.delete()
                    print(f'Subscription {ssn.pk} deleted.')
                    break

