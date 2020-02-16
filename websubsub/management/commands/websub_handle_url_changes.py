import logging
import re
from uuid import uuid4
from urllib.parse import urljoin, urlparse

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import resolve, reverse, Resolver404, NoReverseMatch

from websubsub.models import Subscription
from websubsub.tasks import subscribe

log = logging.getLogger('websubsub')


class Command(BaseCommand):
    help = 'Guess changed urlnames for subscriptions from current callback_url. Also detect changed url patterns and schedule resubscribe with new url.'

    def handle(self, *args, **kwargs):
        self.handle_rebased()
        if self.handle_other():
            self.handle_static()
        
        
    def handle_rebased(self):
        self.rebased = Subscription.objects \
            .filter(callback_url__isnull=False) \
            .exclude(callback_url__startswith=settings.SITE_URL)
        
        if self.rebased.exists():
            print(f'Have you changed SITE_URL to {settings.SITE_URL}?')
            print(f'Found {self.rebased.count()} subscriptions with different base domain.')
            while True:
                answer = input('Fix now? (y/N/show): ')
                if not answer or answer in ('n','N'):
                    break
                if answer == 'show':
                    for ssn in self.rebased:
                        print(
                            f'Subscription {ssn.pk} with topic {ssn.topic} '
                            f'urlname {ssn.callback_urlname} and callback_url '
                            f'{ssn.callback_url}'
                        )
                if answer in ('y', 'Y'):
                    for ssn in self.rebased:
                        path = reverse(ssn.callback_urlname, args=[ssn.id])
                        self.update_url(ssn, urljoin(settings.SITE_URL, path))
                    break
            
            
    def handle_other(self):
        choice_for_all = None
        for ssn in Subscription.objects.exclude(pk__in=self.rebased):
            try:
                resolved_urlname = resolve(urlparse(ssn.callback_url).path).url_name
            except:
                resolved_urlname = None
                
            try:
                path = reverse(ssn.callback_urlname, args=[ssn.id])
            except NoReverseMatch:
                reversed_url = None 
            else:
                reversed_url = urljoin(settings.SITE_URL, path)
                
            if not reversed_url and not resolved_urlname:
                #TODO: fuzzy match by urlname
                print(
                    f'Subscription {ssn.pk} with topic {ssn.topic} has unresolvable '
                    f'urlname {ssn.callback_urlname} and unresolvable callback_url '
                    f'{ssn.callback_url} . You should purge it from database with '
                    './manage.py websub_purge_unresolvable'
                )
                continue
                
            if resolved_urlname == ssn.callback_urlname \
               and reversed_url == ssn.callback_url:
                # No changes detected
                continue
                
            if reversed_url and not ssn.callback_url:
                # Just generate callback url.
                ssn.update(callback_url=ssn.reverse_fullurl())
                continue
            
            # Either url pattern or callback_url have changed
            if choice_for_all == '1' and resolved_urlname:
                self.update_urlname(ssn, resolved_urlname)
                continue
            if choice_for_all == '2' and reversed_url:
                self.update_url(ssn, reversed_url)
                continue
            print(
                f'Subscription {ssn.pk} has urlname {ssn.callback_urlname} '
                f'and url {ssn.callback_url}'
            )
            if not resolved_urlname:
                print('This url does not resolve to this urlname anymore')
            if not reversed_url:
                print('This urlname does not resolve to this url anymore')
                
            print('Please choose what to do with this subscription:')
            choices = []
            if resolved_urlname:
                print(
                    f'  1) Change subscription urlname to {resolved_urlname}\n'
                    f'  1a) ^ Update subscription urlname for all subscriptions'
                )
                choices += ['1', '1a']
            if reversed_url:
                print(
                    f'  2) Change subscription url to {reversed_url}\n'
                    f'  2a) ^ Update subscription url for all subscriptions'
                )
                choices += ['2', '2a']
            print('  3) Exit now')
            choices += ['3']
            while True:
                choice = input(f'Enter your choice ({"/".join(choices)}): ')
                if choice not in choices:
                    continue
                if choice == '3':
                    return False
                if choice in ('1', '1a'):
                    self.update_urlname(ssn, resolved_urlname)
                    choice_for_all = '1' if choice == '1a' else None
                    break
                if choice in ('2', '2a'):
                    self.update_url(ssn, reversed_url)
                    choice_for_all = '2' if choice == '2a' else None
                    break
                        
        return True
        
        
    def update_url(self, ssn, new_url):
        ssn.update(callback_url=new_url)
        print(f'Subscription {ssn.pk} url changed to {new_url}.')
        if ssn.subscribe_status == 'verified':
            subscribe.delay(pk=ssn.pk)
        
        
    def update_urlname(self, ssn, new_urlname):
        #try:
        ssn.update(callback_urlname=new_urlname)
        #except Subscription
        print(f'Subscription {ssn.pk} urlname changed to {new_urlname}.')
        if ssn.subscribe_status == 'verified':
            subscribe.delay(pk=ssn.pk)
        

    def handle_static(self):
        current = []
        for hub_url, hub in settings.WEBSUBS_HUBS.items():
            subscriptions = hub.get('subscriptions', [])
            print(f'Found {len(subscriptions)} static subscriptions for hub {hub_url} in settings.')
            for subscription in subscriptions:
                if isinstance(subscription, tuple):
                    raise Exception(
                        'Static subscription was changed from tuple to dict '
                        '{"topic": topic, "callback_urlname": urlname} in Websubsub version 0.7'
                    )
                try:
                    ssn = Subscription.objects.get(
                        hub_url = hub_url, 
                        topic = subscription['topic'], 
                        callback_urlname = subscription['callback_urlname']
                    )
                except Subscription.DoesNotExist:
                    continue
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
                
