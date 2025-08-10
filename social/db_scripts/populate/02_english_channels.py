# pylint: skip-file
import os
import sys
from time import sleep

import django
from network.models import Channel, Post
from network.tasks import extract_keywords, extract_ner


def initial():
    sys.path.append("../..")
    os.environ["DJANGO_SETTINGS_MODULE"] = "social.settings"
    django.setup()


initial()


english_posts = Post.objects.filter(channel__language=Channel.ENGLISH)
for post in english_posts:
    post.keywords.all().delete()
    extract_keywords.delay(post.id)

sleep(100)

for post in english_posts:
    extract_ner.delay(post.id)
