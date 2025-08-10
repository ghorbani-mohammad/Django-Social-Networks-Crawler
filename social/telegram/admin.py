from django.contrib import admin

from reusable.admins import ReadOnlyAdminDateFieldsMIXIN
from . import models


@admin.register(models.Account)
class AccountAdmin(ReadOnlyAdminDateFieldsMIXIN):
    list_display = ("pk", "created_at", "phone_number", "phone_code_hash")
    readonly_fields = ("phone_code_hash",)
