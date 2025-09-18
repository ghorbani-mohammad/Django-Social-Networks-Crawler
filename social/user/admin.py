import json

from django import forms
from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from reusable.admins import ReadOnlyAdminDateFieldsMIXIN
from . import models
from .services import payment_service


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


@admin.register(models.PaymentInvoice)
class PaymentInvoiceAdmin(ReadOnlyAdminDateFieldsMIXIN):
    list_display = (
        "pk",
        "order_id",
        "profile",
        "subscription_plan_name",
        "status",
        "price_amount",
        "price_currency",
        "payment_url_display",
        "is_paid",
        "created_at",
    )
    list_filter = ("status", "price_currency", "created_at")
    search_fields = (
        "order_id",
        "invoice_id",
        "profile__user__email",
        "customer_email",
        "purchase_id",
    )
    raw_id_fields = ("profile", "subscription")
    readonly_fields = (
        "order_id",
        "invoice_id",
        "payment_url",
        "pay_amount",
        "pay_currency",
        "actually_paid",
        "actually_paid_at_fiat",
        "purchase_id",
        "paid_at",
    )
    actions = ["check_payment_status"]

    fieldsets = (
        (
            "Invoice Information",
            {
                "fields": (
                    "profile",
                    "subscription",
                    "order_id",
                    "invoice_id",
                    "status",
                )
            },
        ),
        (
            "Payment Details",
            {
                "fields": (
                    "price_amount",
                    "price_currency",
                    "pay_amount",
                    "pay_currency",
                    "actually_paid",
                    "actually_paid_at_fiat",
                    "payment_url",
                )
            },
        ),
        (
            "Timing",
            {"fields": ("expires_at", "paid_at")},
        ),
        (
            "Customer Information",
            {"fields": ("customer_email", "order_description")},
        ),
        (
            "Metadata",
            {"fields": ("purchase_id", "metadata")},
        ),
    )

    def subscription_plan_name(self, obj):
        return obj.subscription.plan.name if obj.subscription else "-"

    subscription_plan_name.short_description = "Plan"

    def payment_url_display(self, obj):
        if obj.payment_url:
            return format_html(
                '<a href="{}" target="_blank">Payment Link</a>', obj.payment_url
            )
        return "-"

    payment_url_display.short_description = "Payment URL"

    def is_paid(self, obj):
        if obj.is_paid():
            return format_html('<span style="color: green;">✓ Paid</span>')
        elif obj.is_expired():
            return format_html('<span style="color: red;">✗ Expired</span>')
        elif obj.can_be_paid():
            return format_html('<span style="color: orange;">⏳ Pending</span>')
        else:
            return format_html('<span style="color: gray;">- N/A</span>')

    is_paid.short_description = "Payment Status"

    def check_payment_status(self, request, queryset):
        """
        Admin action to check payment status from third-party service and update local records.
        """
        updated_count = 0
        error_count = 0

        for invoice in queryset:
            try:
                # Get status from payment service
                status_data = payment_service.get_invoice_status(invoice.order_id)
                print(status_data)

                if status_data:
                    # Update invoice with fresh data from payment service
                    old_status = invoice.status
                    invoice.status = status_data.get("status", invoice.status)
                    # Update metadata with sync information
                    invoice.metadata.update(
                        {
                            "last_sync_at": timezone.now().isoformat(),
                            "sync_source": "admin_action",
                            "previous_status": old_status,
                        }
                    )

                    # If payment is finished, mark as paid and activate subscription
                    if status_data.get("status") == "finished" and not invoice.paid_at:
                        invoice.paid_at = timezone.now()

                        # Activate the subscription if it exists
                        if (
                            invoice.subscription
                            and invoice.subscription.status == "pending"
                        ):
                            invoice.subscription.activate()

                            # Update subscription payment reference
                            invoice.subscription.payment_reference = (
                                invoice.purchase_id or invoice.invoice_id
                            )
                            invoice.subscription.save()

                    invoice.save()
                    updated_count += 1
                else:
                    error_count += 1

            except Exception as e:
                error_count += 1
                # Log the error but continue with other invoices
                print(f"Error checking status for invoice {invoice.order_id}: {str(e)}")

        # Show results to admin
        if updated_count > 0:
            self.message_user(
                request,
                f"Successfully updated {updated_count} payment invoice(s).",
                messages.SUCCESS,
            )

        if error_count > 0:
            self.message_user(
                request,
                f"Failed to update {error_count} payment invoice(s). Check logs for details.",
                messages.WARNING,
            )

    check_payment_status.short_description = (
        "Check payment status from third-party service"
    )


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
