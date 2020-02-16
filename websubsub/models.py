import logging
from urllib.parse import urljoin
from uuid import uuid4

from django.db.models import (Model, CharField, IntegerField, TextField, DateTimeField, UUIDField)
from django.conf import settings
from django.urls import reverse


logger = logging.getLogger('websubsub.models')


class Subscription(Model):
    class Meta:
        unique_together = ('hub_url', 'topic', 'callback_urlname')

    id = UUIDField(primary_key=True, default=uuid4, editable=False)
    time_created = DateTimeField(auto_now_add=True)
    time_last_event_received = DateTimeField(null=True, blank=True)
    hub_url = TextField()
    topic = TextField()
    callback_urlname = CharField(max_length=200)
    callback_url = TextField(null=True)  # Generated on subscribe
    lease_expiration_time = DateTimeField(null=True, blank=True)

    STATUS = [
        ('requesting', 'scheduled to be requested asap'),
        ('connerror', 'connection error'),
        ('huberror', 'hub returned error'),
        ('verifying', 'waiting for hub verification request'),
        ('verifyerror', 'hub sent malformed verification request'),
        # 'verified' status merely means that we sent verification challenge
        # back to the hub. It does not mean that hub approved it and (un)subscribed
        # as was requested.
        ('verified', 'verified')
    ]
    SUBSTATUS = STATUS + [('denied', 'hub denied subscription')]

    subscribe_status = CharField(max_length=20, choices=SUBSTATUS, default='requesting')
    unsubscribe_status = CharField(max_length=20, choices=STATUS, null=True, blank=True)

    connerror_count = IntegerField(default=0)
    huberror_count = IntegerField(default=0)
    verifytimeout_count = IntegerField(default=0)
    verifyerror_count = IntegerField(default=0)

    subscribe_attempt_time = DateTimeField(null=True, blank=True)
    unsubscribe_attempt_time = DateTimeField(null=True, blank=True)

    @classmethod
    def create(cls, topic, urlname, hub=None):
        from . import tasks
        if not hub and not settings.WEBSUBS_DEFAULT_HUB_URL:
            raise Exception('Provide hub or set WEBSUBS_DEFAULT_HUB_URL setting.')

        ssn = cls.objects.create(
            topic=topic,
            callback_urlname=urlname,
            hub_url=hub or settings.WEBSUBS_DEFAULT_HUB_URL,
        )
        ssn._subscriberesult = tasks.subscribe.delay(pk=ssn.pk)
        return ssn

    def subscribe(self, urlname=None):
        """
        Reset error counters and schedule to subscribe.
        """
        from . import tasks
        if self.unsubscribe_status is not None:
            logger.warning(f'Resubscribing {self.pk}. Error counters will reset.')
            self.unsubscribe_status = None

        if urlname:
            self.callback_urlname = urlname

        self.connerror_count = 0
        self.huberror_count = 0
        self.verifyerror_count = 0
        self.verifytimeout_count = 0
        self.subscribe_status = 'requesting'
        self.save()

        return tasks.subscribe.delay(pk=self.pk)

    def unsubscribe(self):
        """
        Reset error counters and schedule to unsubscribe.
        """
        from . import tasks

        self.connerror_count = 0
        self.huberror_count = 0
        self.verifyerror_count = 0
        self.verifytimeout_count = 0
        self.unsubscribe_status = 'requesting'
        self.save()

        return tasks.unsubscribe.delay(pk=self.pk)

    def reverse_url(self):
        return reverse(self.callback_urlname, args=(self.pk,))
    
    def reverse_fullurl(self):
        return urljoin(settings.SITE_URL, self.reverse_url())
    
    def update(self, **kwargs):
        """
        Use this method to update and save model instance in single call:

        >>> user.update(email='user@example.com', last_name='Bob')

        is a shortcut for

        >>> user.email = 'user@example.com'
        >>> user.last_name = 'Bob'
        >>> user.save()

        """
        for attr, val in kwargs.items():
            setattr(self, attr, val)

        self.save()
