from __future__ import absolute_import

import os
from logging.config import dictConfig
from django.conf import settings
from celery import Celery
from celery.signals import setup_logging
from celery.schedules import crontab

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "social.settings")
app = Celery("social")

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object("django.conf:settings")
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


@setup_logging.connect
def config_loggers(*_args, **_kwags):
    dictConfig(settings.LOGGING)


app.conf.beat_schedule = {
    "check_channels_crawl": {
        "task": "network.tasks.check_channels_crawl",
        "schedule": crontab(minute=0, hour="*/1"),
    },
    "get_linkedin_feed": {
        "task": "linkedin.tasks.get_linkedin_feed",
        "schedule": crontab(minute=0, hour="*/9"),
    },
    "check_job_pages": {
        "task": "linkedin.tasks.check_job_pages",
        "schedule": crontab(minute="*/15"),
    },
    "check_linkedin_search_pages": {
        "task": "linkedin.tasks.check_expression_search_pages",
        "schedule": crontab(minute=0, hour="*/9"),
    },
    "check_twitter_search_pages": {
        "task": "twitter.tasks.check_twitter_pages",
        "schedule": crontab(minute=0, hour="*/4"),
    },
}
