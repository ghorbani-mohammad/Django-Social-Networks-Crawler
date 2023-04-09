from django.urls import reverse
from django.conf import settings


def url_to_edit_object(obj):
    meta = getattr(obj, "_meta")
    obj_url = reverse(
        f"admin:{meta.app_label}_{meta.model_name}_change",
        args=[obj.id],
    )
    return f"{settings.BACKEND_URL[:-1]}{obj_url}"


class ReadOnlyAdminDateFieldsMIXIN:
    def __init__(self) -> None:
        self.readonly_fields = None

    base_readonly_fields = ("created_at", "updated_at", "deleted_at")

    def get_readonly_fields(self, _request, _obj=None):
        if self.readonly_fields:
            return set(self.readonly_fields + self.base_readonly_fields)
        return self.base_readonly_fields
