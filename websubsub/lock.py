import logging
from contextlib import contextmanager
from functools import wraps
from urllib.parse import urlparse

from django.conf import settings
from redis import StrictRedis
from redis.exceptions import LockError


url = urlparse(settings.WEBSUBS_REDIS_URL)
redis = StrictRedis(host=url.hostname, port=url.port)

logger = logging.getLogger('websubsub.lock')


class TimeoutError(Exception):
    pass


class lock_or_exit(object):
    """
    Decorator. Before decorated function starts, try to acquire redis lock
    with specified key. If lock is acquired successfully, proceed executing
    the function. Otherwise, return immediately.
    The `key` argument can contain templated string, wich will be rendered
    with args and kwargs, passed to the function.

    Example:

    >>> @lock_or_exit('lock_work_{}')
    >>> def workwork(x):
    >>>     pass
    >>>
    >>> workwork(3)  # Will try to acquire redis lock 'lock_work_3'

    """
    def __init__(self, key):
        """ Initalize decorator. """
        self.key = key

    def __call__(self, f):
        """ Decorate the function. """
        @wraps(f)
        def wrapped(*args, **kw):
            key = self.key.format(*args, **kw)
            lock = redis.lock(key, timeout=60)
            have_lock = lock.acquire(blocking_timeout=0)

            if have_lock:
                logger.debug(f'Locked {key}')
            else:
                logger.debug(f'Lock {key} is taken!')
                return

            try:
                return f(*args, **kw)
            finally:
                logger.debug(f'Releasing lock {key}')
                try:
                    lock.release()
                except LockError:
                    # When lock expires, release() could fail.
                    logger.warn(e)

        return wrapped


class lock_wait(object):
    """
    Decorator. Before decorated function starts, try to acquire redis lock
    with specified key, waiting for `waittime` seconds if needed. If lock is
    acquired successfully, proceed executing the function. Otherwise, raise
    TimeoutError.
    The `key` argument can contain templated string, wich will be rendered
    with args and kwargs, passed to the function.

    Example:

    >>> @lock_wait('lock_work_{}', waittime=4)
    >>> def workwork(x):
    >>>     pass
    >>>
    >>> workwork(3)  # Will try to acquire redis lock 'lock_work_3' for 4 seconds

    """
    def __init__(self, key, waittime=10):
        """ Initalize decorator. """
        self.key = key
        self.waittime = waittime

    def __call__(self, f):
        """ Decorate the function. """
        @wraps(f)
        def wrapped(*args, **kw):
            key = self.key.format(*args, **kw)
            lock = redis.lock(key, timeout=60)
            have_lock = lock.acquire(blocking_timeout=self.waittime)

            if have_lock:
                logger.debug(f'Locked {key}')
            else:
                raise TimeoutError(f'Lock {key} is taken!')

            try:
                return f(*args, **kw)
            finally:
                logger.debug(f'Releasing lock {key}')
                try:
                    lock.release()
                except LockError:
                    # When lock expires, release() could fail.
                    logger.warn(e)

        return wrapped

