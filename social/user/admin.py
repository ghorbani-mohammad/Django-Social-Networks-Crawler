from django.contrib import admin

from reusable.admins import ReadOnlyAdminDateFieldsMIXIN
from . import models


@admin.register(models.Profile)
class ProfileAdmin(ReadOnlyAdminDateFieldsMIXIN):
    list_display = ("pk", "user", "cell_number", "chat_id")
