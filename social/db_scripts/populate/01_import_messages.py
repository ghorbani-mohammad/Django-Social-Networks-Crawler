# pylint: skip-file
import os
import random
import sys

import django
from django.utils.timezone import make_aware
from network.models import Channel, Post
from openpyxl import load_workbook


def initial():
    sys.path.append("../..")
    os.environ["DJANGO_SETTINGS_MODULE"] = "social.settings"
    django.setup()


initial()


channel_ids = list(
    Channel.objects.filter(network__name="Telegram").values_list("id", flat=True)
)

sheet = load_workbook(filename="/app/Book1.xlsx").active
texts = [cell.value for cell in sheet["C"]]
dates = [cell.value for cell in sheet["B"]]

for index, text in enumerate(texts):
    index = index + 1
    date = dates[index]
    text = texts[index]
    post = Post.objects.create(
        body=text, channel_id=random.choice(channel_ids), imported=True
    )
    Post.objects.filter(pk=post.pk).update(
        created_at=make_aware(date), updated_at=make_aware(date)
    )
