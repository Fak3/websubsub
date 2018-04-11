import environ

env = environ.Env()

DEBUG = env.bool('DJANGO_DEBUG', default=True)

SECRET_KEY = 'lala'

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'rest_framework',
    'websubsub.apps.WebsubsubConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
]

ROOT_URLCONF = 'tests.djangoproject.urls'

#WSGI_APPLICATION = 'wsgi.application'

DATABASES = {
    'default': env.db('DATABASE_URL'),
}

AUTH_PASSWORD_VALIDATORS = []


LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

CELERY_BROKER_URL = 'memory://'
CELERY_TASK_IGNORE_RESULT = True

CELERY_WORKER_HIJACK_ROOT_LOGGER = False

SITE_URL = 'http://wss.io'
DUMBLOCK_REDIS_URL = ''

WEBSUBS_DEFAULT_HUB_URL = 'http://hub.io'

WEBSUBS_HUBS = {
    WEBSUBS_DEFAULT_HUB_URL: {
        'subscriptions': [('news', 'wscallback'),]
    }
}

