from django.contrib import admin
from django.utils.html import format_html

from reusable.admins import ReadOnlyAdminDateFieldsMIXIN
from . import models


@admin.register(models.Profile)
class ProfileAdmin(ReadOnlyAdminDateFieldsMIXIN):
    list_display = (
        "pk",
        "user",
        "cell_number",
        "chat_id",
        "is_email_verified",
        "verification_attempts",
    )
    list_filter = ("is_email_verified", "created_at", "updated_at")
    search_fields = ("user__email", "user__username", "cell_number", "chat_id")
    readonly_fields = ("verification_code", "verification_expires_at")

    fieldsets = (
        (
            "User Information",
            {"fields": ("user", "cell_number", "chat_id", "about_me")},
        ),
        (
            "Email Verification",
            {
                "fields": (
                    "is_email_verified",
                    "verification_code",
                    "verification_expires_at",
                    "verification_attempts",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj and obj.is_email_verified:
            readonly.extend(
                [
                    "verification_code",
                    "verification_expires_at",
                    "verification_attempts",
                ]
            )
        return readonly
