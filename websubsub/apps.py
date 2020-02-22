import logging
import sys
from urllib.parse import urljoin, urlparse
from uuid import uuid4

from django.apps import AppConfig
from django.conf import settings
from django.urls import reverse, resolve, Resolver404, NoReverseMatch


logger = logging.getLogger('websubsub.apps')


class ImproperlyConfigured(Exception):
    pass

            
class WebsubsubConfig(AppConfig):
    name = 'websubsub'

    required_settings = [
        'DUMBLOCK_REDIS_URL',
        'WEBSUBSUB_OWN_ROOTURL'
    ]
    WEBSUBSUB_MAX_CONNECT_RETRIES = 2
    WEBSUBSUB_MAX_HUB_ERROR_RETRIES = 2
    WEBSUBSUB_MAX_VERIFY_RETRIES = 2
    WEBSUBSUB_VERIFY_WAIT_TIME = 60  # seconds
    WEBSUBSUB_HUBS = {}
    WEBSUBSUB_DEFAULT_HUB_URL = None
    WEBSUBSUB_AUTOFIX_URLS = True

    def ready(self):
        # Initialize settings with default values.
        for name in dir(self):
            if name.isupper() and not hasattr(settings, name):
                setattr(settings, name, getattr(self, name))
                
        argv = ' '.join(sys.argv)
        if 'test' in argv or 'pytest' in argv or 'py.test' in argv:
            return
        
        if 'websubscribe_static' in argv:
            # websubscribe_static calls checks by itself after it is finished.
            return
        
        if 'makemigrations' in argv or 'migrate' in argv or 'collectstatic' in argv:
            return
            
        if 'runserver' in argv or 'wsgi' in argv or 'asgi' in argv or 'websub_' in argv:
            self.check_required_settings()
            self.check_static_subscriptions()
            self.check_hub_url_slash_consistency()
            self.check_urls_resolve()

    def check_required_settings(self):
        # Check if required settings are defined.
        for name in self.required_settings:
            if not hasattr(settings, name):
                logger.warning(f'settings.{name} is required')


    def check_static_subscriptions(self):
        from .models import Subscription
        current = set()
        
        # Check if all static subscriptions urlnames properly resolve to urls.
        for hub_url, hub in settings.WEBSUBSUB_HUBS.items():
            for ssn in hub.get('subscriptions', []):
                current.add((hub_url, ssn['callback_urlname'], ssn['topic']))
                try:
                    reverse(ssn['callback_urlname'], args=[uuid4()])
                except NoReverseMatch:
                    logger.error(
                        f'NoReverseMatch for static subscription {ssn}. '
                        'Please change callback_urlname to the correct one.'
                    )
                dbssn = Subscription.objects.filter(
                    static=True, 
                    hub_url=hub_url, 
                    callback_urlname=ssn['callback_urlname'],
                    topic=ssn['topic'],
                )
                if not dbssn.exists():
                    logger.error(
                        f'Static subscription {ssn} declared in your settings does not '
                        f'exist in the database. Run `./manage.py websub_static_subscribe` '
                        f'to create it.'
                    )
                    
        # Find orphan static subscriptions
        for ssn in Subscription.objects.filter(static=True):
            if (ssn.hub_url, ssn.callback_urlname, ssn.topic) not in current:
                logger.error(
                    f'Found orphan static subscription {ssn.pk} in the database:\n'
                    f'  topic: {ssn.topic}\n'
                    f'  hub: {ssn.hub_url}\n'
                    f'  callback_urlname: {ssn.callback_urlname}\n'
                    f'You can purge old static subscriptions from the database using '
                    '`./manage.py websub_static_subscribe --purge-orphans`'
                )

    def check_hub_url_slash_consistency(self):
        from .models import Subscription
        hubs = list(Subscription.objects.values_list('hub_url', flat=True))
        with_slash = set(x for x in hubs if x.endswith('/'))
        no_slash = set(x for x in hubs if not x.endswith('/'))
        doubles = set()
        for hub in no_slash:
            if hub + '/' in with_slash:
                doubles.add(hub)
        if doubles:
            logger.error(
                f'Following hub urls are used inconsistently with and '
                f'without trailing slash: {doubles}'
            )
            
    def check_urls_resolve(self):
        from .models import Subscription
        
        # Check if all existing subscriptions urlnames properly reverse to urls.
        unreversable_count = 0
        for ssn in Subscription.objects.all():
            try:
                reverse(ssn.callback_urlname, args=[uuid4()])
            except NoReverseMatch:
                unreversable_count += 1
        if unreversable_count:
            logger.error(
                f'Have you changed urls? Found '
                f'{unreversable_count} subscriptions with unresolvable urlname. '
                'Go to django admin interface and set correct urlname for these subscriptions. '
                'Or run `./manage.py websub_handle_url_changes` to guess new urlname from '
                'subscription callback_url. Or run `./manage.py websub_purge_unresolvable` to '
                'remove all unresolvable subscriptions from database.'
            )
            
        # Check if settings.WEBSUBSUB_OWN_ROOTURL was changed
        rebased = Subscription.objects \
            .filter(callback_url__isnull=False) \
            .exclude(callback_url__startswith=settings.WEBSUBSUB_OWN_ROOTURL)
        
        if rebased.exists():
            logger.error(
                f'Have you changed WEBSUBSUB_OWN_ROOTURL to {settings.WEBSUBSUB_OWN_ROOTURL} ? '
                f'Found {rebased.count()} subscriptions with different base domain. '
                'Run `./manage.py websub_handle_url_changes` to fix urls and resubscribe.'
            )
                
        # Check if all subscriptions callback_url resolves to urlname
        unresolvabe_count = 0
        for ssn in Subscription.objects.filter(subscribe_status='verified').exclude(pk__in=rebased):
            try:
                resolve(urlparse(ssn.callback_url).path).url_name
            except Resolver404:
                unresolvabe_count += 1
                
        if unresolvabe_count:
            logger.error(
                f'Have you changed urls? Found {unresolvabe_count} active subscriptions '
                'with callback url that does not resolve anymore. '
                'Run `./manage.py websub_handle_url_changes` to fix urls and resubscribe.'
            )
