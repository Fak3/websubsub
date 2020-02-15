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
        choice_for_all = None
        
        rebased = Subscription.objects \
            .filter(callback_url__isnull=False) \
            .exclude(callback_url__startswith=settings.SITE_URL)
        
        if rebased.exists():
            print(f'Have you changed SITE_URL to {settings.SITE_URL}?')
            print(f'Found {rebased.count()} subscriptions with different base domain.')
            while True:
                answer = input('Fix now? (y/N/show): ')
                if not answer or answer in ('n','N'):
                    break
                if answer == 'show':
                    for ssn in rebased:
                        print(
                            f'Subscription {ssn.pk} with topic {ssn.topic} '
                            f'urlname {ssn.callback_urlname} and callback_url '
                            f'{ssn.callback_url}'
                        )
                if answer in ('y', 'Y'):
                    for ssn in rebased:
                        path = reverse(ssn.callback_urlname, args=[ssn.id])
                        self.update_url(ssn, urljoin(settings.SITE_URL, path))
            
        for ssn in Subscription.objects.exclude(pk__in=rebased):
            try:
                cur_resolved = resolve(urlparse(ssn.callback_url).path)
            except:
                cur_resolved = None
                
            try:
                path = reverse(ssn.callback_urlname, args=[ssn.id])
            except NoReverseMatch:
                reversed_urlpattern = '' 
            else:
                # Trim uuid.
                full_url = urljoin(settings.SITE_URL, path)
                reversed_urlpattern = re.sub(f'{ssn.id}(/?)$', '', full_url) 
                
            if not reversed_urlpattern and not cur_resolved:
                #TODO: fuzzy match by urlname
                print(
                    f'Subscription {ssn.pk} with topic {ssn.topic} has unresolvable '
                    f'urlname {ssn.callback_urlname} and unresolvable callback_url '
                    f'{ssn.callback_url} . You should purge it from database with '
                    './manage.py websub_purge_unresolvable'
                )
                continue
                
            if cur_resolved and cur_resolved.url_name == ssn.callback_urlname \
               and reversed_urlpattern and ssn.callback_url.startswith(reversed_urlpattern):
                # No changes detected
                continue
                
            # Either url pattern or callback_url have changed
            if choice_for_all == '1' and cur_resolved:
                self.update_urlname(ssn, cur_resolved.url_name)
                continue
            if choice_for_all == '2' and reversed_urlpattern:
                self.update_url(ssn, full_url)
                continue
            print(
                f'Subscription {ssn.pk} has urlname {ssn.callback_urlname} '
                f'and url {ssn.callback_url}'
            )
            if not cur_resolved:
                print('This url does not resolve to this urlname anymore')
            if not reversed_urlpattern:
                print('This urlname does not resolve to this url anymore')
                
            print('Please choose what to do with this subscription:')
            import ipdb; ipdb.sset_trace()
            choices = []
            if cur_resolved:
                print(
                    f'  1) Change subscription urlname to {cur_resolved.url_name}\n'
                    f'  1a) ^ Update subscription urlname for all subscriptions'
                )
                choices += ['1', '1a']
            if reversed_urlpattern:
                print(
                    f'  2) Change subscription url to {full_url}\n'
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
                    return
                if choice in ('1', '1a'):
                    self.update_urlname(ssn, cur_resolved.url_name)
                    choice_for_all = '1' if choice == '1a' else None
                    break
                if choice in ('2', '2a'):
                    self.update_url(ssn, full_url)
                    choice_for_all = '2' if choice == '2a' else None
                    break
                        
    def update_url(self, ssn, new_url):
        ssn.update(callback_url=new_url)
        print(f'Subscription {ssn.pk} url changed to {full_url}.')
        if ssn.subscribe_status == 'verified':
            subscribe.delay(pk=ssn.pk)
        
    def update_urlname(self, ssn, new_urlname):
        #try:
        ssn.update(callback_urlname=new_urlname)
        #except Subscription
        print(f'Subscription {ssn.pk} urlname changed to {new_urlname}.')
        if ssn.subscribe_status == 'verified':
            subscribe.delay(pk=ssn.pk)
        
