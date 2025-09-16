import json

from django import forms
from django.contrib import admin
from django.utils.html import format_html

from reusable.admins import ReadOnlyAdminDateFieldsMIXIN
from . import models


class SubscriptionPlanForm(forms.ModelForm):
    """Custom form for SubscriptionPlan with better JSON handling."""

    features = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "cols": 50}),
        help_text='Enter features as a JSON array. Example: ["Feature 1", "Feature 2", "Feature 3"]',
        initial="[]",
    )

    class Meta:
        model = models.SubscriptionPlan
        fields = "__all__"

    def clean_features(self):
        features_data = self.cleaned_data.get("features")
        if not features_data:
            return []

        try:
            # Try to parse as JSON
            parsed_features = json.loads(features_data)
            if not isinstance(parsed_features, list):
                raise forms.ValidationError("Features must be a JSON array (list).")
            return parsed_features
        except json.JSONDecodeError as e:
            raise forms.ValidationError(f"Invalid JSON format: {str(e)}")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Convert existing features to JSON string for display
        if self.instance and self.instance.pk and self.instance.features:
            self.fields["features"].initial = json.dumps(
                self.instance.features, indent=2
            )


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


@admin.register(models.SubscriptionPlan)
class SubscriptionPlanAdmin(ReadOnlyAdminDateFieldsMIXIN):
    form = SubscriptionPlanForm

    list_display = (
        "pk",
        "name",
        "plan_type",
        "price",
        "duration_days",
        "is_active",
        "created_at",
    )
    list_filter = ("plan_type", "is_active", "created_at")
    search_fields = ("name", "description")

    fieldsets = (
        (
            "Plan Information",
            {"fields": ("name", "plan_type", "price", "duration_days", "is_active")},
        ),
        (
            "Features & Description",
            {
                "fields": ("features", "description"),
                "description": 'Enter features as a JSON array. Example: ["Unlimited posts", "Advanced analytics", "Priority support"]',
            },
        ),
    )


@admin.register(models.Subscription)
class SubscriptionAdmin(ReadOnlyAdminDateFieldsMIXIN):
    list_display = (
        "pk",
        "profile",
        "plan",
        "status",
        "is_active",
        "starts_at",
        "expires_at",
        "days_remaining_display",
    )
    list_filter = ("status", "is_active", "plan__plan_type", "created_at")
    search_fields = (
        "profile__user__email",
        "profile__cell_number",
        "payment_reference",
    )
    raw_id_fields = ("profile",)

    fieldsets = (
        (
            "Subscription Information",
            {"fields": ("profile", "plan", "status", "is_active")},
        ),
        (
            "Dates",
            {"fields": ("starts_at", "expires_at", "auto_renew")},
        ),
        (
            "Payment",
            {"fields": ("payment_reference",)},
        ),
    )

    def days_remaining_display(self, obj):
        days = obj.days_remaining()
        if days > 0:
            return format_html('<span style="color: green;">{} days</span>', days)
        else:
            return format_html('<span style="color: red;">Expired</span>')

    days_remaining_display.short_description = "Days Remaining"


@admin.register(models.FeatureUsage)
class FeatureUsageAdmin(ReadOnlyAdminDateFieldsMIXIN):
    list_display = (
        "pk",
        "profile",
        "feature_type",
        "usage_count",
        "last_used",
    )
    list_filter = ("feature_type", "last_used")
    search_fields = ("profile__user__email", "profile__cell_number")
    raw_id_fields = ("profile",)

    fieldsets = (
        (
            "Usage Information",
            {"fields": ("profile", "feature_type", "usage_count", "last_used")},
        ),
        (
            "Metadata",
            {"fields": ("metadata",)},
        ),
    )
