from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Profile

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
