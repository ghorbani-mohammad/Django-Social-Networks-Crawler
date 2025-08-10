from django.contrib import admin
from django.utils.html import format_html

from reusable.admins import ReadOnlyAdminDateFieldsMIXIN
from . import models, tasks


@admin.register(models.SearchPage)
class SearchPageAdmin(ReadOnlyAdminDateFieldsMIXIN):
    list_display = (
        "pk",
        "name",
        "page_link",
        "enable",
        "output_channel",
        "last_crawl_at",
    )

    def page_link(self, obj):
        return format_html("<a href='{url}'>Link</a>", url=obj.url)

    def crawl_page_action(self, request, queryset):
        for page in queryset:
            tasks.crawl_search_page.delay(page.id)

    actions = (crawl_page_action,)
    readonly_fields = ("last_crawl_at",)
