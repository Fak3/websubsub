# Websubsub

[![Build Status](https://travis-ci.org/Fak3/websubsub.svg?branch=master)](https://travis-ci.org/Fak3/websubsub)
[![codecov](https://codecov.io/gh/Fak3/websubsub/branch/master/graph/badge.svg)](https://codecov.io/gh/Fak3/websubsub)
![Support Python versions 3.6, 3.7 and 3.8](https://img.shields.io/badge/python-3.6%2C%203.7%2C%203.8-blue.svg)
[![pypi-version](https://img.shields.io/pypi/v/websubsub.svg)](https://pypi.python.org/pypi/websubsub)

Django websub subscriber.

## Installation

```
pip install websubsub
```

Add `websubsub.apps.WebsubsubConfig` to the list of `INSTALLED_APPS` in your `settings.py`:

```
INSTALLED_APPS = [
    ...,
    'websubsub.apps.WebsubsubConfig'
]
```

Set the `WEBSUBSUB_OWN_ROOTURL` setting in your `settings.py` to the full url of your project 
site, e.g. `https://example.com/`. It will be used to build full callback urls.

Set `DUMBLOCK_REDIS_URL` settings in your `settings.py`. Redis locks are used to ensure
subscription/unsubscription tasks are consistent with hub and local database.

```
WEBSUBSUB_OWN_ROOTURL = 'http://example.com/'
DUMBLOCK_REDIS_URL= 'redis://redishost:6379'
```

Add `websubsub.tasks.refresh_subscriptions` and `websubsub.tasks.retry_failed` to celerybeat
schedule. If you define it in `settings.py`:

```
CELERY_BEAT_SCHEDULE = {
    'websub_refresh': {
        'task': 'websubsub.tasks.refresh_subscriptions',
        'schedule': 3600  # Hourly
    },
    'websub_retry': {
        'task': 'websubsub.tasks.retry_failed',
        'schedule': 600  # Every 10 minutes
    },
}
```

## Usage

### Create Websub callback
Create celery task handler, usually in `tasks.py`:

```
from celery import shared_task

@shared_task
def news_task(data):
    print('got news!')
```

Callback url should end with uuid. Register url for handler in `urls.py`:

```
from websubsub.views import WssView
from .tasks import news_task, reports_task

urlpatterns = [
    path('/websubcallback/news/<uuid:id>', WssView.as_view(news_task), name='webnews')
    path('/websubcallback/reports/<uuid:id>', WssView.as_view(reports_task), name='webreports')
]
```

### Subscribe

You can create subscription on the go, or use static subscriptions.

To create subscription in the code:

```
from websubsub.models import Subscription
Subscription.create(topic='mytopic', urlname='webnews', hub='http://example.com')
```

This will create Subscription object in the database and schedule celery task
to subscribe with hub.

#### Static subscriptions

Static subscriptions can be defined in your `settings.py`, they are then materialized
with management command `./manage.py websub_static_subscribe`.

Add static subscriptions in your `settings.py`:

```
WEBSUBSUB_HUBS = {
    'http://example.com': {
        'subscriptions': [
            {'topic': 'mytopic', 'callback_urlname': 'webnews'},
            ...
        ]
    }
}
```

Execute `./manage.py websub_static_subscribe`

### Unsubscribe

To unsubscribe existing subscription, call `Subscription.unsubscribe()` method:

```
from websubsub.models import Subscription
Subscription.objects.get(pk=4).unsubscribe()
```


## Settings

_WEBSUBSUB_OWN_ROOTURL_ - ex.: `https://example.com/`. Required. Will be used to build full callback urls.

_DUMBLOCK_REDIS_URL_ - ex.: `redis://redishost:6379`. Required. Will be used to lock atomic tasks.

_WEBSUBSUB_AUTOFIX_URLS_ - If `True`, then `websubsub.tasks.subscribe()` task will be allowed to ovewrite subscription.callback_url, resolving its callback_urlname. If False, it will print an error and exit. Default: `True`

_WEBSUBSUB_DEFAULT_HUB_URL_

_WEBSUBSUB_MAX_CONNECT_RETRIES_

_WEBSUBSUB_MAX_HUB_ERROR_RETRIES_

_WEBSUBSUB_MAX_VERIFY_RETRIES_

_WEBSUBSUB_VERIFY_WAIT_TIME_ - How many seconds should pass before unverified subscription is
considered failed. After that time, `websubsub.tasks.retry_failed()` task will be able to retry
subscription process again.

## Management commands

`./manage.py websub_static_subscribe` - Materialize static subscriptions from settings. Optional arguments:

* `--purge-orphans` - delete old static subscriptions from database
* `-y`, `--yes` - answer yes to all
* `--reset-counters` - reset retry counters
* `--force` - send new subscription request to hub even if already subscribed or explicitly unsubscribed

`./manage.py websub_purge_unresolvable` - Delete all subscriptions with unresolvable urlname from database.

`./manage.py websub_purge_all` - Delete all subscriptions from database.

`./manage.py websub_reset_counters` - Reset retry counters for all subscriptions in database.

`./manage.py websub_handle_url_changes` - Guess changed urlnames for subscriptions from current callback_url. Also detect changed url patterns and schedule resubscribe with new url.

`./manage.py dumpdata websubsub --indent 2` - Show all subscriptions.

## Testing

```
pip install -r tests/requirements.txt
py.test
```
