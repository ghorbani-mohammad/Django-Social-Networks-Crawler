from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (api_view, authentication_classes,
                                       permission_classes)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import \
    TokenRefreshView as DRFTokenRefreshView

from .models import Profile
from .serializers import (EmailVerificationConfirmSerializer,
                          EmailVerificationRequestSerializer,
                          ProfileSerializer, UserRegistrationSerializer,
                          UserSerializer)

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


@api_view(["POST"])
@permission_classes([AllowAny])
def request_email_verification(request):
    """Request email verification code"""
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


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_email_code(request):
    """Verify email code and return JWT tokens"""
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
            {"error": "Invalid verification code"}, status=status.HTTP_400_BAD_REQUEST
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


@api_view(["POST"])
@permission_classes([AllowAny])
def register_user(request):
    """Register a new user with email verification"""
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


@api_view(["GET"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Get current user profile"""
    serializer = UserSerializer(request.user)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET", "PUT", "PATCH"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def profile_detail(request):
    """Get or update user profile"""
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=request.user)

    if request.method == "GET":
        serializer = ProfileSerializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method in ["PUT", "PATCH"]:
        serializer = ProfileSerializer(
            profile, data=request.data, partial=request.method == "PATCH"
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def refresh_token(request):
    """Refresh JWT access token"""
    refresh_token = request.data.get("refresh")

    if not refresh_token:
        return Response(
            {"error": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST
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
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]
