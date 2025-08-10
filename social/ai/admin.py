from django.contrib import admin

from reusable.admins import ReadOnlyAdminDateFieldsMIXIN
from . import models


@admin.register(models.CoverLetter)
class CoverLetterAdmin(ReadOnlyAdminDateFieldsMIXIN):
    list_display = ("pk", "profile", "created_at")
    readonly_fields = ("cover_letter",)
