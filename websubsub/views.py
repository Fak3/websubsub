import logging
from datetime import timedelta

from django.conf import settings
from django.http import HttpResponse
from django.utils.decorators import classonlymethod
from django.utils.timezone import now
from rest_framework.views import APIView  # TODO: can we live without drf dependency?
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST

from .models import Subscription


logger = logging.getLogger('websubsub.views')


class WssView(APIView):
    """
    Generic websub callback processing.

    Usage:

    Create a celery task that will accept incoming data, then in your urls.py:

    >>> from websubsub.views import WssView
    >>> from .tasks import news_task, reports_task
    >>>
    >>> urlpatterns = [
    >>>     path('/websubcallback/news/<uuid:id>', WssView.as_view(news_task), name='webnews')
    >>>     path('/websubcallback/reports/<uuid:id>', WssView.as_view(reports_task), name='webreports')
    >>> ]

    """

    @classonlymethod
    def as_view(cls, handler_task, *args, **kwargs):
        result = super().as_view(*args, **kwargs)
        result.handler_task = handler_task
        return result

    def get(self, request, *args, **kwargs):
        """
        Hub sends GET request to callback url to verify subscription/unsubscription or
        to inform about subscription denial.
        """
        if 'hub.topic' not in request.GET:
            logger.error(f'{request.path}: GET request is missing hub.topic')
            return Response('Missing hub.topic', status=HTTP_400_BAD_REQUEST)

        mode = request.GET.get('hub.mode', None)
        if mode not in ['subscribe', 'unsubscribe', 'denied']:
            logger.error(f'{request.path}: GET request received unknown hub.mode "{mode}"')
            return Response('Missing or unknown hub.mode', status=HTTP_400_BAD_REQUEST)

        try:
            ssn = Subscription.objects.get(topic=request.GET['hub.topic'])
        except Subscription.DoesNotExist:
            ssn = None

        if mode == 'subscribe':
            return self.on_subscribe(request, ssn)
        elif mode == 'unsubscribe':
            return self.on_unsubscribe(request, ssn)
        elif mode == 'denied':
            return self.on_denied(request, ssn)

    def on_subscribe(self, request, ssn):
        """
        The subscriber MUST confirm that the hub.topic corresponds to a pending
        subscription or unsubscription that it wishes to carry out. If so, the
        subscriber MUST respond with an HTTP success (2xx) code with a response
        body equal to the hub.challenge parameter. If the subscriber does not
        agree with the action, the subscriber MUST respond with a 404 "Not Found"
        response.
        Hubs MAY make the hub.lease_seconds equal to the value the subscriber
        passed in their subscription request but MAY change the value depending
        on the hub's policies. To sustain a subscription, the subscriber MUST
        re-request the subscription on the hub before hub.lease_seconds seconds
        has elapsed.
        Hubs MUST enforce lease expirations, and MUST NOT issue perpetual lease
        durations.
        """
        if not ssn:
            logger.error(
                f'Received unwanted subscription verification request with'
                f' topic {request.GET["hub.topic"]}!')
            return Response('Unwanted subscription', status=HTTP_400_BAD_REQUEST)

        if 'hub.challenge' not in request.GET:
            logger.error(f'Missing hub.topic in subscription verification {ssn.pk}!')
            ssn.subscribe_status = 'verifyerror'
            ssn.verifyerror_count += 1
            ssn.save()
            return Response('Missing hub.challenge', status=HTTP_400_BAD_REQUEST)

        if not request.GET.get('hub.lease_seconds', '').isdigit():
            logger.error(f'Missing integer hub.lease_seconds in subscription verification {ssn.pk}!')
            ssn.subscribe_status = 'verifyerror'
            ssn.verifyerror_count += 1
            ssn.save()
            return Response('hub.lease_seconds required and must be integer', status=HTTP_400_BAD_REQUEST)

        if ssn.unsubscribe_status is not None:
            logger.error(f'Subscription {ssn.pk} received subscription verification request,'
                         f' but its was explicitly unsubscribed before.')
            return Response('Unsubscribed')

        if ssn.subscribe_status != 'verifying':
            logger.error(f'Subscription {ssn.pk} received subscription verification request,'
                         f' but its status is "{ssn.get_subscribe_status_display()}"')
            # TODO: should we ignore it?

        ssn.subscribe_status = 'verified'
        ssn.lease_expiration_time = now() + timedelta(seconds=int(request.GET['hub.lease_seconds']))
        ssn.connerror_count = 0
        ssn.huberror_count = 0
        ssn.verifyerror_count = 0
        ssn.verifytimeout_count = 0
        ssn.save()
        logger.info(f'Subscription {ssn.pk} verified')
        return HttpResponse(request.GET['hub.challenge'])

    def on_unsubscribe(self, request, ssn):
        # TODO
        return HttpResponse(request.GET['hub.challenge'])

    def on_denied(self, request, ssn):
        """
        TODO
        If (and when), the subscription is denied, the hub MUST inform the subscriber by
        sending an HTTP GET request to the subscriber's callback URL as given in the
        subscription request. This request has the following query string arguments appended:
        hub.mode - REQUIRED. The literal string "denied".
        hub.topic -REQUIRED. The topic URL given in the corresponding subscription request.
        hub.reason -OPTIONAL. The hub may include a reason for which the subscription has been denied.

        Hubs may provide an additional HTTP Location header to indicate that the subscriber may
        retry subscribing to a different hub.topic. This allows for limited distribution to
        specific groups or users in the context of social web applications.

        The subscription MAY be denied by the hub at any point (even if it was previously accepted).
        The Subscriber SHOULD then consider that the subscription is not possible anymore.
        """
        if not ssn:
            logger.error(f'Received denial on unwanted subscription with '
                         f'topic {request.GET["hub.topic"]}!')
            return Response('Unwanted subscription')

        logger.error(f'Hub denied subscription {ssn.pk}!')
        ssn.update(subscribe_status='denied')
        return Response('')


    def post(request, *args, **kwargs):
        """
        The subscriber's callback URL MUST return an HTTP 2xx response code to
        indicate a success. The subscriber's callback URL MAY return an HTTP 410
        code to indicate that the subscription has been deleted, and the hub MAY
        terminate the subscription if it receives that code as a response. The hub
        MUST consider all other subscriber response codes as failures
        Subscribers SHOULD respond to notifications as quickly as possible; their
        success response code SHOULD only indicate receipt of the message, not
        acknowledgment that it was successfully processed by the subscriber.
        """
        try:
            self.handler_task.delay(request.data)
        except:
            pass
        finally:
            return Response('')  # TODO

