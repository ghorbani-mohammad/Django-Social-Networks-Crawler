from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from rest_framework import serializers

from .models import (FeatureUsage, PaymentInvoice, Profile, Subscription,
                     SubscriptionPlan)

User = get_user_model()


class EmailVerificationRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower()


class EmailVerificationConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6, min_length=6)

    def validate_email(self, value):
        return value.lower()

    def validate_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("Code must contain only digits")
        return value


class UserRegistrationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    verification_code = serializers.CharField(
        max_length=6, min_length=6, write_only=True
    )

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "verification_code")
        extra_kwargs = {
            "first_name": {"required": False},
            "last_name": {"required": False},
        }

    def validate_email(self, value):
        return value.lower()

    def validate_verification_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError(
                "Verification code must contain only digits"
            )
        return value

    def validate(self, attrs):
        email = attrs["email"]
        code = attrs["verification_code"]

        # Check if user exists and get their profile
        try:
            user = User.objects.get(email=email)
            profile = user.profile
        except User.DoesNotExist:
            raise serializers.ValidationError(
                "User not found. Please request a verification code first."
            )

        if not profile.verification_code or profile.verification_code != code:
            raise serializers.ValidationError("Invalid verification code")

        if profile.is_verification_expired():
            raise serializers.ValidationError("Verification code has expired")

        if not profile.can_attempt_verification():
            raise serializers.ValidationError(
                "Too many failed attempts. Please request a new code."
            )

        # Mark as verified
        profile.mark_email_as_verified()
        attrs["profile"] = profile

        return attrs

    def create(self, validated_data):
        email = validated_data["email"]
        profile = validated_data["profile"]
        user = profile.user

        # Update user information if provided
        if "first_name" in validated_data:
            user.first_name = validated_data["first_name"]
        if "last_name" in validated_data:
            user.last_name = validated_data["last_name"]
        user.save()

        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "date_joined")
        read_only_fields = ("id", "date_joined")


class ProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Profile
        fields = (
            "id",
            "user",
            "cell_number",
            "chat_id",
            "about_me",
            "email",
            "additional_notes",
            "education_background",
            "professional_experience",
            "is_email_verified",
        )
        read_only_fields = ("id", "user")


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Serializer for subscription plans."""

    class Meta:
        model = SubscriptionPlan
        fields = [
            "id",
            "name",
            "plan_type",
            "price",
            "duration_days",
            "features",
            "description",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for user subscriptions."""

    plan = SubscriptionPlanSerializer(read_only=True)
    plan_id = serializers.IntegerField(write_only=True)
    days_remaining = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            "id",
            "plan",
            "plan_id",
            "status",
            "starts_at",
            "expires_at",
            "is_active",
            "auto_renew",
            "days_remaining",
            "is_expired",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "profile", "created_at", "updated_at", "expires_at"]

    def get_days_remaining(self, obj):
        return obj.days_remaining()

    def get_is_expired(self, obj):
        return obj.is_expired()

    def create(self, validated_data):
        plan_id = validated_data.pop("plan_id")
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError("Invalid subscription plan.")

        validated_data["plan"] = plan
        validated_data["profile"] = self.context["request"].user.profile

        return super().create(validated_data)


class PaymentInvoiceSerializer(serializers.ModelSerializer):
    """Serializer for payment invoices."""

    subscription_plan_name = serializers.CharField(
        source="subscription.plan.name", read_only=True
    )
    is_paid = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    can_be_paid = serializers.SerializerMethodField()

    class Meta:
        model = PaymentInvoice
        fields = [
            "id",
            "order_id",
            "invoice_id",
            "payment_url",
            "price_amount",
            "price_currency",
            "pay_amount",
            "pay_currency",
            "actually_paid",
            "actually_paid_at_fiat",
            "status",
            "purchase_id",
            "expires_at",
            "paid_at",
            "customer_email",
            "order_description",
            "subscription_plan_name",
            "is_paid",
            "is_expired",
            "can_be_paid",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "profile",
            "subscription",
            "order_id",
            "invoice_id",
            "payment_url",
            "pay_amount",
            "pay_currency",
            "actually_paid",
            "actually_paid_at_fiat",
            "purchase_id",
            "paid_at",
            "created_at",
            "updated_at",
        ]

    def get_is_paid(self, obj):
        return obj.is_paid()

    def get_is_expired(self, obj):
        return obj.is_expired()

    def get_can_be_paid(self, obj):
        return obj.can_be_paid()


class FeatureUsageSerializer(serializers.ModelSerializer):
    """Serializer for feature usage tracking."""

    feature_type_display = serializers.CharField(
        source="get_feature_type_display", read_only=True
    )

    class Meta:
        model = FeatureUsage
        fields = [
            "id",
            "feature_type",
            "feature_type_display",
            "usage_count",
            "last_used",
            "metadata",
        ]
        read_only_fields = ["id", "profile", "last_used"]
