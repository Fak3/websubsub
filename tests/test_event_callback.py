from uuid import uuid4
import re

import responses
from django.test import override_settings
from django.urls import path
from model_mommy.mommy import make
from unittest.mock import patch, Mock, MagicMock
from websubsub.views import WssView

from .base import BaseTestCase, method_url_body


urlpatterns = []

@override_settings(ROOT_URLCONF='tests.test_event_callback')
class EventCallbackTest(BaseTestCase):
    """
    When hub sends POST request to callback, task should be called with request data.
    """
    def test_event(self):
        # GIVEN WssView with websub handler task
        task = Mock()
        urlpatterns.append(path('websubcallback/<uuid:id>', WssView.as_view(task)))
        
        # WHEN hub posts json data to the callback
        response = self.client.post(
            '/websubcallback/472ee3ef-a10f-48f8-9da2-5400ed22a883', {'test': 'ok'}
        )

        # THEN response status_code should be 200 (ok)
        assert response.status_code == 200
        
        # AND task.delay() should be called with json data
        task.delay.assert_called_once_with({'test': 'ok'})
