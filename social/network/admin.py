import redis

from django.contrib import admin
from reusable.other import TIME_FORMAT
from reusable.admins import ReadOnlyAdminDateFieldsMIXIN

from twitter import tasks as twi_tasks
from linkedin import tasks as lin_tasks
from . import models


@admin.register(models.Network)
class NetworkAdmin(ReadOnlyAdminDateFieldsMIXIN):
    list_display = (
        "pk",
        "name",
        "url",
        "status",
        "today_posts_count",
        "today_posts_count",
    )


@admin.register(models.Channel)
class ChannelAdmin(ReadOnlyAdminDateFieldsMIXIN):
    list_display = (
        "pk",
        "name",
        "network",
        "username",
        "language",
        "crawl_interval",
        "get_last_crawl",
        "status",
        "joined",
        "today_posts_count",
        "created_at",
    )
    list_filter = ("network", "language")

    @admin.display(ordering="last_crawl", description="last_crawl")
    def get_last_crawl(self, instance):
        if instance.last_crawl:
            return instance.last_crawl.strftime(TIME_FORMAT)
        return None

    def crawl(self, _request, queryset):
        for channel in queryset:
            if channel.network.name == "Twitter":
                twi_tasks.get_twitter_posts.delay(channel.pk)
            elif channel.network.name == "Linkedin":
                lin_tasks.get_linkedin_posts.delay(channel.pk)

    actions = (crawl,)


@admin.register(models.Post)
class PostAdmin(ReadOnlyAdminDateFieldsMIXIN):
    list_display = (
        "pk",
        "channel",
        "short_body",
        "views_count",
        "share_count",
        "get_created_at",
    )
    list_filter = ("channel__network",)

    @admin.display(ordering="created_at", description="created_at")
    def get_created_at(self, instance):
        return instance.created_at.strftime(TIME_FORMAT)


@admin.register(models.Keyword)
class KeywordAdmin(ReadOnlyAdminDateFieldsMIXIN):
    list_display = (
        "pk",
        "keyword",
        "ignored",
        "get_post",
        "get_created_at",
    )
    raw_id_fields = ("post",)

    @admin.display(ordering="created_at", description="created_at")
    def get_created_at(self, instance):
        return instance.created_at.strftime(TIME_FORMAT)

    @admin.display(ordering="post", description="post")
    def get_post(self, instance):
        return instance.post.admin_link


@admin.register(models.Backup)
class BackupAdmin(ReadOnlyAdminDateFieldsMIXIN, admin.ModelAdmin):
    list_display = (
        "pk",
        "link",
        "status",
        "type",
        "get_created_at",
        "get_updated_at",
    )

    @admin.display(ordering="created_at", description="created_at")
    def get_created_at(self, instance):
        return instance.created_at.strftime(TIME_FORMAT)

    @admin.display(ordering="updated_at", description="updated_at")
    def get_updated_at(self, instance):
        return instance.updated_at.strftime(TIME_FORMAT)


@admin.register(models.Config)
class ConfigAdmin(ReadOnlyAdminDateFieldsMIXIN, admin.ModelAdmin):
    list_display = ("pk", "crawl_linkedin_feed")

    def flush_views_cache(self, _request, _queryset):
        redis_db = redis.StrictRedis(host="social_redis", port=6379, db=15)
        redis_db.flushdb()

    actions = (flush_views_cache,)


@admin.register(models.ChannelListExport)
class ChannelListExportAdmin(ReadOnlyAdminDateFieldsMIXIN, admin.ModelAdmin):
    list_display = ("pk", "file", "created_at")


@admin.register(models.IgnoredKeyword)
class IgnoredKeywordAdmin(ReadOnlyAdminDateFieldsMIXIN, admin.ModelAdmin):
    list_display = ("pk", "keyword", "created_at")


@admin.register(models.BlockedKeyword)
class BlockedKeywordAdmin(ReadOnlyAdminDateFieldsMIXIN, admin.ModelAdmin):
    list_display = ("pk", "keyword", "created_at")


@admin.register(models.Log)
class LogAdmin(admin.ModelAdmin):
    list_filter = ("level",)
    readonly_fields = ("time", "level", "message")
    list_display = ("pk", "level", "short_message", "time")

    def delete_all_logs(self, request, queryset):
        models.Log.objects.all().delete()

    actions = (delete_all_logs,)
