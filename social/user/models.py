import secrets
from datetime import timedelta

from django.db import models
from django.utils import timezone

from reusable.models import BaseModel


class Profile(BaseModel):
    user = models.OneToOneField("auth.User", on_delete=models.CASCADE)
    cell_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    chat_id = models.CharField(max_length=15, unique=True, null=True, blank=True)
    about_me = models.TextField(null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    additional_notes = models.TextField(null=True, blank=True)
    education_background = models.TextField(null=True, blank=True)
    professional_experience = models.TextField(null=True, blank=True)

    # Email verification fields
    verification_code = models.CharField(max_length=6, null=True, blank=True)
    verification_expires_at = models.DateTimeField(null=True, blank=True)
    verification_attempts = models.IntegerField(default=0)
    is_email_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"({self.pk} - {self.cell_number or self.user.email})"

    def save(self, *args, **kwargs):
        if not self.verification_code and not self.is_email_verified:
            self.verification_code = self.generate_verification_code()
        if not self.verification_expires_at and not self.is_email_verified:
            self.verification_expires_at = timezone.now() + timedelta(minutes=10)
        super().save(*args, **kwargs)

    @staticmethod
    def generate_verification_code():
        return str(secrets.randbelow(900000) + 100000)

    def is_verification_expired(self):
        if not self.verification_expires_at:
            return True
        return timezone.now() > self.verification_expires_at

    def can_attempt_verification(self):
        max_attempts = 3
        return (
            self.verification_attempts < max_attempts
            and not self.is_verification_expired()
        )

    def increment_verification_attempts(self):
        self.verification_attempts += 1
        self.save(update_fields=["verification_attempts"])

    def mark_email_as_verified(self):
        self.is_email_verified = True
        self.verification_code = None
        self.verification_expires_at = None
        self.verification_attempts = 0
        self.save(
            update_fields=[
                "is_email_verified",
                "verification_code",
                "verification_expires_at",
                "verification_attempts",
            ]
        )

    def reset_verification_code(self):
        self.verification_code = self.generate_verification_code()
        self.verification_expires_at = timezone.now() + timedelta(minutes=10)
        self.verification_attempts = 0
        self.save(
            update_fields=[
                "verification_code",
                "verification_expires_at",
                "verification_attempts",
            ]
        )

    def add_favorite_job(self, job):
        """Add a job to user's favorites."""
        from linkedin.models import FavoriteJob

        favorite, created = FavoriteJob.objects.get_or_create(profile=self, job=job)
        return favorite, created

    def remove_favorite_job(self, job):
        """Remove a job from user's favorites."""
        from linkedin.models import FavoriteJob

        try:
            favorite = FavoriteJob.objects.get(profile=self, job=job)
            favorite.delete()
            return True
        except FavoriteJob.DoesNotExist:
            return False

    def is_job_favorite(self, job):
        """Check if a job is in user's favorites."""
        from linkedin.models import FavoriteJob

        return FavoriteJob.objects.filter(profile=self, job=job).exists()

    def get_favorite_jobs(self):
        """Get all favorite jobs for this user."""
        from linkedin.models import Job

        return Job.objects.filter(favorited_by__profile=self).order_by("-created_at")

    def has_active_premium_subscription(self):
        """Check if user has an active premium subscription."""
        return Subscription.objects.filter(
            profile=self, is_active=True, expires_at__gt=timezone.now()
        ).exists()

    def get_active_subscription(self):
        """Get the user's active subscription if any."""
        try:
            return Subscription.objects.get(
                profile=self, is_active=True, expires_at__gt=timezone.now()
            )
        except Subscription.DoesNotExist:
            return None


class SubscriptionPlan(BaseModel):
    """Subscription plan model for different pricing tiers."""

    PLAN_TYPES = [
        ("monthly", "Monthly"),
        ("yearly", "Yearly"),
    ]

    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField(help_text="Duration in days")
    features = models.JSONField(default=list, help_text="List of features included")
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ["name", "plan_type"]

    def __str__(self):
        return f"{self.name} - {self.get_plan_type_display()}"


class Subscription(BaseModel):
    """User subscription model."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
        ("pending", "Pending"),
    ]

    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="subscriptions"
    )
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    starts_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    payment_reference = models.CharField(max_length=255, blank=True, null=True)
    auto_renew = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.profile} - {self.plan} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = self.starts_at + timedelta(days=self.plan.duration_days)
        super().save(*args, **kwargs)

    def is_expired(self):
        """Check if subscription is expired."""
        return timezone.now() > self.expires_at

    def days_remaining(self):
        """Get days remaining in subscription."""
        if self.is_expired():
            return 0
        return (self.expires_at - timezone.now()).days

    def activate(self):
        """Activate the subscription."""
        # Deactivate any existing active subscriptions for this profile
        Subscription.objects.filter(profile=self.profile, is_active=True).update(
            is_active=False, status="cancelled"
        )

        self.is_active = True
        self.status = "active"
        self.save()

    def cancel(self):
        """Cancel the subscription and associated payment invoices."""
        self.is_active = False
        self.status = "cancelled"
        self.save()

        # Cancel any pending payment invoices for this subscription
        pending_invoices = self.payment_invoices.filter(
            status__in=["waiting", "confirming", "confirmed", "partially_paid"]
        )
        for invoice in pending_invoices:
            invoice.cancel()


class PaymentInvoice(BaseModel):
    """Track cryptocurrency payment invoices from NodeJS payment service."""

    STATUS_CHOICES = [
        ("waiting", "Waiting for Payment"),
        ("confirming", "Confirming Payment"),
        ("confirmed", "Payment Confirmed"),
        ("sending", "Processing Payment"),
        ("partially_paid", "Partially Paid"),
        ("finished", "Payment Completed"),
        ("failed", "Payment Failed"),
        ("refunded", "Payment Refunded"),
        ("expired", "Invoice Expired"),
        ("cancelled", "Payment Cancelled"),
    ]

    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="payment_invoices"
    )
    subscription = models.ForeignKey(
        "Subscription",
        on_delete=models.CASCADE,
        related_name="payment_invoices",
        null=True,
        blank=True,
    )

    # Payment service fields
    order_id = models.CharField(max_length=255, unique=True)
    invoice_id = models.CharField(max_length=255, blank=True, null=True)
    payment_url = models.URLField(blank=True, null=True)

    # Amount fields
    price_amount = models.DecimalField(max_digits=10, decimal_places=2)
    price_currency = models.CharField(max_length=10, default="USD")
    pay_amount = models.DecimalField(
        max_digits=20, decimal_places=8, null=True, blank=True
    )
    pay_currency = models.CharField(max_length=10, blank=True, null=True)
    actually_paid = models.DecimalField(
        max_digits=20, decimal_places=8, null=True, blank=True
    )
    actually_paid_at_fiat = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    # Status and metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="waiting")
    purchase_id = models.CharField(max_length=255, blank=True, null=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    # Additional metadata
    customer_email = models.EmailField()
    order_description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invoice {self.order_id} - {self.status} (${self.price_amount})"

    def is_paid(self):
        """Check if invoice is paid successfully."""
        return self.status == "finished"

    def is_expired(self):
        """Check if invoice is expired."""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at

    def can_be_paid(self):
        """Check if invoice can still be paid."""
        return (
            self.status in ["waiting", "confirming", "confirmed", "partially_paid"]
            and not self.is_expired()
        )

    def can_be_cancelled(self):
        """Check if invoice can be cancelled."""
        return self.status in ["waiting", "confirming", "confirmed", "partially_paid"]

    def cancel(self):
        """Cancel the payment invoice and associated subscription if applicable."""
        if self.can_be_cancelled():
            # Try to cancel via payment service first
            from .services import payment_service

            try:
                payment_service.cancel_invoice(self.invoice_id)
            except Exception:
                # Continue with local cancellation even if service call fails
                pass

            self.status = "cancelled"
            self.save()

            # Cancel associated subscription if it exists and is still pending
            if self.subscription and self.subscription.status == "pending":
                self.subscription.cancel()

            return True
        return False


class FeatureUsage(BaseModel):
    """Track premium feature usage for users."""

    FEATURE_TYPES = [
        ("ai_cover_letter", "AI Cover Letter Generation"),
        ("advanced_search", "Advanced Job Search"),
        ("priority_support", "Priority Customer Support"),
    ]

    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="feature_usage"
    )
    feature_type = models.CharField(max_length=50, choices=FEATURE_TYPES)
    usage_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(auto_now=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ["profile", "feature_type"]

    def __str__(self):
        return f"{self.profile} - {self.get_feature_type_display()}: {self.usage_count}"

    def increment_usage(self, metadata=None):
        """Increment usage count for this feature."""
        self.usage_count += 1
        if metadata:
            self.metadata.update(metadata)
        self.save()
