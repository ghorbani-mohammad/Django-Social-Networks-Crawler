from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import \
    TokenRefreshView as DRFTokenRefreshView

from .models import FeatureUsage, Profile, Subscription, SubscriptionPlan
from .serializers import (EmailVerificationConfirmSerializer,
                          EmailVerificationRequestSerializer,
                          FeatureUsageSerializer, ProfileSerializer,
                          SubscriptionPlanSerializer, SubscriptionSerializer,
                          UserRegistrationSerializer, UserSerializer)

User = get_user_model()


def send_verification_email(email, code):
    """Send verification code to user's email"""
    subject = "Email Verification Code"
    message = f"""
    Your verification code is: {code}
    
    This code will expire in 10 minutes.
    
    If you didn't request this code, please ignore this email.
    """

    send_mail(
        subject,
        message,
        f"Job AI Assistant <{settings.EMAIL_HOST_USER}>",
        [email],
        fail_silently=False,
    )


class RequestEmailVerificationView(APIView):
    """Request email verification code"""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EmailVerificationRequestSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]

        # Get or create user and profile
        user, created = User.objects.get_or_create(
            email=email, defaults={"username": email, "is_active": True}
        )

        profile, profile_created = Profile.objects.get_or_create(user=user)

        # Reset verification code for existing profiles
        if not profile_created:
            profile.reset_verification_code()

        # Send email
        try:
            send_verification_email(email, profile.verification_code)
            return Response(
                {"message": "Verification code sent successfully"},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": "Failed to send verification email"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class VerifyEmailCodeView(APIView):
    """Verify email code and return JWT tokens"""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EmailVerificationConfirmSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        code = serializer.validated_data["code"]

        try:
            user = User.objects.get(email=email)
            profile = user.profile
        except User.DoesNotExist:
            return Response(
                {"error": "User not found. Please request a verification code first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not profile.verification_code or profile.verification_code != code:
            profile.increment_verification_attempts()
            return Response(
                {"error": "Invalid verification code"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if profile.is_verification_expired():
            return Response(
                {"error": "Verification code has expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not profile.can_attempt_verification():
            return Response(
                {"error": "Too many failed attempts. Please request a new code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark as verified
        profile.mark_email_as_verified()

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token

        return Response(
            {
                "message": "Email verified successfully",
                "user": UserSerializer(user).data,
                "tokens": {"access": str(access_token), "refresh": str(refresh)},
                "is_new_user": False,  # User already exists at this point
            },
            status=status.HTTP_200_OK,
        )


class RegisterUserView(APIView):
    """Register a new user with email verification"""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        try:
            user = serializer.save()

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token

            return Response(
                {
                    "message": "User registered successfully",
                    "user": UserSerializer(user).data,
                    "tokens": {"access": str(access_token), "refresh": str(refresh)},
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    """Get current user profile"""

    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProfileDetailView(APIView):
    """Get or update user profile"""

    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            profile = Profile.objects.create(user=request.user)

        serializer = ProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            profile = Profile.objects.create(user=request.user)

        serializer = ProfileSerializer(profile, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        try:
            profile = request.user.profile
        except Profile.DoesNotExist:
            profile = Profile.objects.create(user=request.user)

        serializer = ProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class RefreshTokenView(APIView):
    """Refresh JWT access token"""

    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"error": "Refresh token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            refresh = RefreshToken(refresh_token)
            access_token = refresh.access_token

            return Response(
                {"access": str(access_token), "refresh": str(refresh)},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": "Invalid refresh token"}, status=status.HTTP_400_BAD_REQUEST
            )


# Custom TokenRefreshView with explicit authentication
class TokenRefreshView(DRFTokenRefreshView):
    permission_classes = [AllowAny]


class SubscriptionPlansView(APIView):
    """Get all available subscription plans."""

    permission_classes = [AllowAny]

    def get(self, request):
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by("price")
        serializer = SubscriptionPlanSerializer(plans, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserSubscriptionsView(APIView):
    """Get user's subscriptions or create a new subscription."""

    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        subscriptions = Subscription.objects.filter(profile=request.user.profile)
        serializer = SubscriptionSerializer(subscriptions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = SubscriptionSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            subscription = serializer.save()
            # In a real implementation, you would integrate with a payment processor here
            # For now, we'll just activate the subscription
            subscription.activate()
            return Response(
                SubscriptionSerializer(subscription).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CurrentSubscriptionView(APIView):
    """Get user's current active subscription."""

    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        subscription = request.user.profile.get_active_subscription()

        if subscription:
            serializer = SubscriptionSerializer(subscription)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "No active subscription found"},
                status=status.HTTP_404_NOT_FOUND,
            )


class CancelSubscriptionView(APIView):
    """Cancel a user's subscription."""

    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, subscription_id):
        try:
            subscription = Subscription.objects.get(
                id=subscription_id, profile=request.user.profile, is_active=True
            )
            subscription.cancel()
            return Response(
                {"message": "Subscription cancelled successfully"},
                status=status.HTTP_200_OK,
            )
        except Subscription.DoesNotExist:
            return Response(
                {"error": "Subscription not found"}, status=status.HTTP_404_NOT_FOUND
            )


class FeatureUsageView(APIView):
    """Get user's premium feature usage statistics."""

    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        usage_stats = FeatureUsage.objects.filter(profile=request.user.profile)
        serializer = FeatureUsageSerializer(usage_stats, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PremiumStatusView(APIView):
    """Check if user has premium access and return subscription details."""

    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = request.user.profile
        has_premium = profile.has_active_premium_subscription()
        active_subscription = profile.get_active_subscription()

        data = {
            "has_premium": has_premium,
            "subscription": SubscriptionSerializer(active_subscription).data
            if active_subscription
            else None,
        }

        return Response(data, status=status.HTTP_200_OK)
