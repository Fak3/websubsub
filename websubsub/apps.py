from uuid import uuid4
import logging
import sys

from django.apps import AppConfig
from django.conf import settings
from django.urls import reverse


logger = logging.getLogger('websubsub.apps')


class ImproperlyConfigured(Exception):
    pass


class WebsubsubConfig(AppConfig):
    name = 'websubsub'

    required_settings = [
        'WEBSUBS_REDIS_URL',
        'SITE_URL'
    ]
    WEBSUBS_MAX_CONNECT_RETRIES = 2
    WEBSUBS_MAX_HUB_ERROR_RETRIES = 2
    WEBSUBS_MAX_VERIFY_RETRIES = 2
    WEBSUBS_VERIFY_WAIT_TIME = 60  # seconds
    WEBSUBS_HUBS = {}

    def ready(self):
        self.configure()

        if 'test' not in sys.argv and 'pytest' not in sys.argv:
            # TODO: check that existing subscription callback urls resolve
            pass

    def configure(self):
        for name in dir(self):
            if name.isupper() and not hasattr(settings, name):
                setattr(settings, name, getattr(self, name))

        for name in self.required_settings:
            if not hasattr(settings, name):
                raise ImproperlyConfigured(f'settings.{name} is required')

        for hub_url, hub in settings.WEBSUBS_HUBS.items():
            for topic, urlname in hub.get('subscriptions', []):
                reverse(urlname, args=[uuid4()])
