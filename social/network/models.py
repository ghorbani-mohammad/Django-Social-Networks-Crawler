from os import path

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.template.defaultfilters import truncatechars
from django.utils import timezone
from django.utils.html import format_html

from linkedin import tasks as lin_tasks
from reusable.admins import url_to_edit_object
from reusable.models import BaseModel
from twitter import tasks as twi_tasks
from . import tasks


def channel_list_export_path(_instance, filename):
    ext = filename.split(".")[-1].lower()
    return path.join(
        ".",
        "static",
        "export",
        "channel",
        f"{int(timezone.now().timestamp())}.{ext}",
    )


class Tag(BaseModel):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return f"({self.pk} - {self.name})"


class Network(BaseModel):
    name = models.CharField(max_length=100)
    url = models.URLField()
    status = models.BooleanField(default=True)

    @property
    def today_posts_count(self):
        counter = 0
        for channel in self.channels.all():
            counter += channel.posts.count()
        return counter

    def __str__(self):
        return f"({self.pk} - {self.name})"


class Channel(BaseModel):
    name = models.CharField(max_length=100, null=True, blank=True)
    username = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    network = models.ForeignKey(
        Network, on_delete=models.CASCADE, related_name="channels"
    )
    status = models.BooleanField(default=True)
    data = models.JSONField(null=True, blank=True)
    joined = models.BooleanField(null=True, blank=True)
    tags = models.ManyToManyField(Tag, related_name="channels", blank=True)
    last_crawl = models.DateTimeField(null=True, blank=True)
    crawl_interval = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1)]
    )
    PERSIAN = "persian"
    ENGLISH = "english"
    LANGUAGE_CHOICES = ((PERSIAN, PERSIAN), (ENGLISH, ENGLISH))
    language = models.CharField(
        choices=LANGUAGE_CHOICES, max_length=15, default=PERSIAN, blank=True
    )

    class Meta:
        unique_together = ("network", "username")

    @property
    def today_posts_count(self):
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.posts.filter(created_at__gte=today).count()

    def __str__(self):
        return f"({self.pk} - {self.name} - {self.network})"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.network.name == "Linkedin":
                if self.last_crawl is None:
                    transaction.on_commit(
                        lambda: lin_tasks.get_linkedin_posts.delay(self.pk)
                    )
            elif self.network.name == "Twitter":
                if self.last_crawl is None:
                    transaction.on_commit(
                        lambda: twi_tasks.get_twitter_posts.delay(self.pk)
                    )
            elif self.network.name == "Telegram":
                self.username = self.username.replace("https://t.me/", "")
            super().save(*args, **kwargs)


class Post(BaseModel):
    body = models.TextField()
    network_id = models.CharField(max_length=200, null=True, blank=True)
    channel = models.ForeignKey(
        Channel, on_delete=models.CASCADE, related_name="posts", null=True
    )
    views_count = models.IntegerField(null=True, blank=True)
    share_count = models.IntegerField(null=True, blank=True)
    data = models.JSONField(null=True)
    imported = models.BooleanField(default=False, null=True, blank=True)
    sentiment = models.JSONField(null=True, blank=True)
    category = models.JSONField(null=True, blank=True)
    main_category_title = models.CharField(max_length=50, null=True, blank=True)
    ner = models.JSONField(null=True, blank=True)

    @property
    def admin_link(self):
        url = url_to_edit_object(self)
        return format_html("<a href='{url}'>{post}</a>", url=url, post=self)

    @property
    def short_body(self):
        return self.body[: min(100, len(self.body) - 1)]

    @property
    def sorted_sentiment(self):
        if self.sentiment:
            return dict(sorted(self.sentiment.items(), key=lambda item: item[1]))
        return None

    def __str__(self):
        return f"({self.pk} - {self.channel})"

    def save(self, *args, **kwargs):
        if len(self.body.replace(" ", "")) < 5:
            print("length below 5")
            return
        created = self.pk is None
        with transaction.atomic():
            if created:
                self.views_count = self.views_count or 0
                self.share_count = self.share_count or 0
                if settings.ENVIRONMENT == settings.PRODUCTION:
                    transaction.on_commit(lambda: tasks.extract_keywords.delay(self.pk))
                    transaction.on_commit(lambda: tasks.extract_ner.delay(self.pk))
                    transaction.on_commit(
                        lambda: tasks.extract_sentiment.delay(self.pk)
                    )
                    transaction.on_commit(
                        lambda: tasks.extract_categories.delay(self.pk)
                    )
            super().save(*args, **kwargs)


class Keyword(BaseModel):
    post = models.ForeignKey(
        Post,
        related_name="keywords",
        related_query_name="keyword",
        on_delete=models.CASCADE,
    )
    keyword = models.CharField(max_length=100)
    ignored = models.BooleanField(default=False)

    def __str__(self):
        return f"({self.pk} - {self.keyword})"


class Backup(BaseModel):
    link = models.CharField(max_length=300, null=True, blank=True)
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    STATUS_CHOICES = ((PROCESSING, PROCESSING), (COMPLETED, COMPLETED))
    status = models.CharField(choices=STATUS_CHOICES, max_length=15, default=PROCESSING)
    RASAD_1 = "RASAD_1"
    RASAD_2 = "RASAD_2"
    TYPE_CHOICES = ((RASAD_1, RASAD_1), (RASAD_2, RASAD_2))
    type = models.CharField(choices=TYPE_CHOICES, max_length=15, default=RASAD_1)

    def __str__(self):
        return f"({self.pk} - {self.created_at})"

    def save(self, *args, **kwargs):
        created = self.pk is None
        with transaction.atomic():
            if created:
                transaction.on_commit(lambda: tasks.take_backup.delay(self.pk))
            super().save(*args, **kwargs)


class Config(BaseModel):
    crawl_linkedin_feed = models.BooleanField(default=False)


class ChannelListExport(BaseModel):
    file = models.FileField(upload_to=channel_list_export_path, null=True, blank=True)

    def save(self, *args, **kwargs):
        created = self.pk is None
        with transaction.atomic():
            if created:
                transaction.on_commit(lambda: tasks.export_channel_list.delay(self.pk))
            super().save(*args, **kwargs)


class IgnoredKeyword(BaseModel):
    keyword = models.CharField(max_length=100)

    def __str__(self):
        return f"({self.pk} - {self.keyword})"


class BlockedKeyword(BaseModel):
    keyword = models.CharField(max_length=100)

    def __str__(self):
        return f"({self.pk} - {self.keyword})"


class Log(models.Model):
    time = models.DateTimeField(auto_now_add=True)
    level = models.CharField(max_length=10)
    message = models.TextField()

    @property
    def short_message(self):
        return truncatechars(self.message, 50)
