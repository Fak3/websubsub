import logging

from django.conf import settings
from django.utils.decorators import classonlymethod
from rest_framework.views import APIView  # TODO: can we live without drf dependency?
from rest_framework.response import Response


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

    def get(self, request):
        if request.data['hub.mode'] == 'subscribe':
            return self.on_subscribe(request.data)
        elif data['hub.mode'] == 'unsubscribe':
            return self.on_unsubscribe(request.data)
        elif data['hub.mode'] == 'denied':
            return self.on_denied(request.data)

    def on_subscribe(self, data):
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
        try:
            ssn = Subscription.objects.get(topic=data['hub.topic'])
        except Subscription.DoesNotExist:
            logger.error(
                f'Received unwanted subscription verification request with'
                f' topic {data["hub.topic"]}!')
            return Response('unwanted subscription')

        if ssn.unsubscribe_status is not None:
            logger.error(f'Subscription {ssn.pk} received subscription verification request,'
                         f' but its was explicitly unsubscribed before.')
            return Response('unsubscribed')

        if ssn.subscribe_status != 'verifying':
            logger.error(f'Subscription {ssn.pk} received subscription verification request,'
                         f' but its status is "{ssn.get_subscribe_status_display()}"')
            # TODO: should we ignore it?

        ssn.subscribe_status = 'verified'
        ssn.save()
        logger.info(f'Subscription {ssn.pk} verified')
        return Response(data['hub.challenge'])

    def on_unsubscribe(self, data):
        # TODO
        return Response(data['hub.challenge'])

    def on_denied(self, data):
        # TODO
        logging.error('Hub denied subscription!')
        return Response('')


    def post(request):
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

