from django.contrib import admin
from django.utils.html import format_html

from . import models, tasks
from reusable.admins import ReadOnlyAdminDateFieldsMIXIN


@admin.register(models.JobSearch)
class JobSearchAdmin(ReadOnlyAdminDateFieldsMIXIN):
    readonly_fields = ("last_crawl_at", "last_crawl_count")
    list_display = (
        "pk",
        "profile",
        "name",
        "page_link",
        "enable",
        "just_easily_apply",
        "priority",
        "page_count",
        "ignoring_filters_count",
        "output_channel",
        "last_crawl_at",
        "last_crawl_count",
    )
    ordering = ("enable", "-last_crawl_at")

    def page_link(self, obj):
        return format_html("<a href='{url}'>Link</a>", url=obj.url)

    @admin.action(description="Crawl page")
    def crawl_page_action(self, request, queryset):
        for page in queryset:
            tasks.get_job_page_posts.delay(page.pk)

    @admin.action(description="Crawl page (ignore repetitive)")
    def crawl_page_repetitive_action(self, request, queryset):
        for page in queryset:
            tasks.get_job_page_posts.delay(page.pk, ignore_repetitive=False)

    actions = (crawl_page_action, crawl_page_repetitive_action)


@admin.register(models.IgnoredJob)
class IgnoredJobAdmin(ReadOnlyAdminDateFieldsMIXIN):
    list_display = (
        "pk",
        "title",
        "location",
        "company",
        "language",
        "reason",
        "job_url",
        "created_at",
    )
    readonly_fields = tuple(
        field.name for field in models.IgnoredJob._meta.get_fields()
    )
    list_filter = ("reason",)

    def job_url(self, obj: models.IgnoredJob):
        return format_html("<a href='{url}'>Link</a>", url=obj.url)

    def remove_all_objects(self, request, _queryset):
        models.IgnoredJob.objects.all().delete()

    actions = (remove_all_objects,)

    def has_add_permission(self, request):
        return False


@admin.register(models.Keyword)
class KeywordAdmin(ReadOnlyAdminDateFieldsMIXIN):
    list_display = ("pk", "name", "created_at")


@admin.register(models.IgnoringFilter)
class IgnoringFilterAdmin(ReadOnlyAdminDateFieldsMIXIN):
    list_display = ("pk", "place", "keyword", "enable", "created_at", "updated_at")
    list_filter = ("place",)
    search_fields = ("keyword",)


@admin.register(models.ExpressionSearch)
class ExpressionSearchAdmin(ReadOnlyAdminDateFieldsMIXIN):
    list_display = ("pk", "name", "page_link", "enable", "last_crawl_at", "created_at")
    readonly_fields = ("last_crawl_at",)

    def page_link(self, obj):
        return format_html("<a href='{url}'>Link</a>", url=obj.url)

    @admin.action(description="Crawl page")
    def crawl_page_action(self, request, queryset):
        for page in queryset:
            tasks.get_expression_search_posts.delay(page.pk)

    @admin.action(description="Crawl page repetitive")
    def crawl_page_repetitive_action(self, request, queryset):
        for page in queryset:
            tasks.get_expression_search_posts.delay(page.pk, ignore_repetitive=False)

    actions = (crawl_page_action, crawl_page_repetitive_action)
