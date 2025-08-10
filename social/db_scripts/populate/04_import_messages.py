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

sheet = load_workbook(filename="/app/messages.xlsx").active
texts = [cell.value for cell in sheet["F"]]
dates = [cell.value for cell in sheet["C"]]

success_counter = 0
failure_counter = 0
date_counter = {}
for index, text in enumerate(texts):
    try:
        index = index + 1
        date = dates[index]
        date_counter[str(date).split()[0]] = (
            date_counter.get(str(date).split()[0], 0) + 1
        )
        text = texts[index]
        post = Post.objects.create(
            body=text, channel_id=random.choice(channel_ids), imported=True
        )
        Post.objects.filter(pk=post.pk).update(
            created_at=make_aware(date), updated_at=make_aware(date)
        )
        success_counter += 1
    except:
        failure_counter += 1

print(f"success counter: {success_counter}")
print(f"failure counter: {failure_counter}")
print(date_counter)
