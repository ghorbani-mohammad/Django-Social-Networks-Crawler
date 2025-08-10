# pylint: skip-file
import datetime
import os
import sys

import django
from network.models import Keyword


def initial():
    sys.path.append("../..")
    os.environ["DJANGO_SETTINGS_MODULE"] = "social.settings"
    django.setup()


initial()


today = datetime.date.today()

keywords = Keyword.objects.filter(created_at__date=today)

for keyword in keywords:
    Keyword.objects.filter(pk=keyword.pk).update(
        created_at=keyword.post.created_at, updated_at=keyword.post.updated_at
    )
