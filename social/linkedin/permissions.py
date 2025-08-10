from django.conf import settings
from rest_framework.permissions import BasePermission


class HasPublicAPIKey(BasePermission):
    message = "Invalid or missing API key"

    def has_permission(self, request, _view):
        api_key = (
            request.query_params.get("api_key")
            or request.headers.get("X-API-KEY")
            or request.META.get("HTTP_X_API_KEY")
        )
        expected = getattr(settings, "PUBLIC_API_KEY", None)
        return bool(expected) and api_key == expected
