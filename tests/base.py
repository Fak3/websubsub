from unittest.mock import patch
from urllib.parse import parse_qs

import responses
from mockredis import mock_strict_redis_client
from rest_framework.test import APITestCase


def method_url_body(rcall):
    return (rcall.request.method, rcall.request.url, parse_qs(rcall.request.body))


class BaseTestCase(APITestCase):
    def _pre_setup(self):
        """
        Mock requests and redis.
        """
        super()._pre_setup()

        responses.start()
        patch('websubsub.lock.redis', mock_strict_redis_client()).start()

    def _post_teardown(self):
        """
        Disable all mocks after the test.
        """
        super()._post_teardown()

        responses.reset()
        responses.stop()
        patch.stopall()

