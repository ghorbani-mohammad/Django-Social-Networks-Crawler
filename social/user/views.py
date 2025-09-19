from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import \
    TokenRefreshView as DRFTokenRefreshView

from .models import (FeatureUsage, PaymentInvoice, Profile, Subscription,
                     SubscriptionPlan)
from .serializers import (EmailVerificationConfirmSerializer,
                          EmailVerificationRequestSerializer,
                          FeatureUsageSerializer, PaymentInvoiceSerializer,
                          ProfileSerializer, SubscriptionPlanSerializer,
                          SubscriptionSerializer, UserRegistrationSerializer,
                          UserSerializer)
from .services import payment_service
from network.views import ListPagination

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

            try:
                # Create payment invoice using the payment service
                payment_invoice = payment_service.create_invoice(
                    profile=request.user.profile,
                    subscription=subscription,
                    price_amount=subscription.plan.price,
                    price_currency="USD",
                    success_url=request.data.get("success_url"),
                    cancel_url=request.data.get("cancel_url"),
                    failure_url=request.data.get("failure_url"),
                )

                return Response(
                    {
                        "message": "Subscription created. Please complete payment.",
                        "subscription": SubscriptionSerializer(subscription).data,
                        "payment": PaymentInvoiceSerializer(payment_invoice).data,
                    },
                    status=status.HTTP_201_CREATED,
                )

            except Exception as e:
                # If payment service fails, delete the subscription and return error
                subscription.delete()
                return Response(
                    {"error": f"Payment service error: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
                {"subscription": None, "message": "No active subscription found"},
                status=status.HTTP_200_OK,
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

            # Cancel the subscription (this will also cancel associated payment invoices)
            subscription.cancel()

            # Get count of cancelled payment invoices for response
            cancelled_invoices_count = subscription.payment_invoices.filter(
                status="expired"
            ).count()

            response_message = "Subscription cancelled successfully"
            if cancelled_invoices_count > 0:
                response_message += (
                    f" and {cancelled_invoices_count} pending payment(s) cancelled"
                )

            return Response(
                {"message": response_message},
                status=status.HTTP_200_OK,
            )
        except Subscription.DoesNotExist:
            return Response(
                {"error": "Subscription not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to cancel subscription: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
        latest_subscription = profile.get_latest_subscription()
        
        # Determine has_premium value: "active", "pending", or False
        if not latest_subscription:
            has_premium = False
        elif latest_subscription.status == "active":
            has_premium = "active"
        elif latest_subscription.status == "pending":
            has_premium = "pending"
        else:
            # For expired, cancelled, or any other status
            has_premium = False

        data = {
            "has_premium": has_premium,
            "subscription": SubscriptionSerializer(latest_subscription).data
            if latest_subscription
            else None,
        }

        return Response(data, status=status.HTTP_200_OK)


class PaymentInvoicesView(ListAPIView):
    """Get user's payment invoices."""

    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentInvoiceSerializer
    pagination_class = ListPagination

    def get_queryset(self):
        return PaymentInvoice.objects.filter(profile=self.request.user.profile).order_by("-created_at")


class PaymentInvoiceDetailView(APIView):
    """Get specific payment invoice details."""

    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, invoice_id):
        try:
            invoice = PaymentInvoice.objects.get(
                id=invoice_id, profile=request.user.profile
            )

            # Try to get updated status from payment service
            try:
                payment_status = payment_service.get_invoice_status(invoice.order_id)
                if payment_status and payment_status.get("status"):
                    # Update local status if different
                    if invoice.status != payment_status["status"]:
                        invoice.status = payment_status["status"]
                        invoice.save()
            except Exception:
                pass  # Continue with local data if service is unavailable

            serializer = PaymentInvoiceSerializer(invoice)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except PaymentInvoice.DoesNotExist:
            return Response(
                {"error": "Payment invoice not found"}, status=status.HTTP_404_NOT_FOUND
            )


class PaymentWebhookView(APIView):
    """Handle payment webhook notifications from NodeJS payment service."""

    permission_classes = [AllowAny]

    def post(self, request):
        """Process payment webhook."""
        try:
            webhook_data = request.data

            # Process the webhook data
            success = payment_service.process_webhook_data(webhook_data)

            if success:
                return Response(
                    {"message": "Webhook processed successfully"},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"error": "Failed to process webhook"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except Exception as e:
            return Response(
                {"error": f"Webhook processing error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CancelPaymentInvoiceView(APIView):
    """Cancel a specific payment invoice."""

    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, invoice_id):
        """Cancel a payment invoice."""
        try:
            invoice = PaymentInvoice.objects.get(
                id=invoice_id, profile=request.user.profile
            )

            # Check if invoice can be cancelled
            if not invoice.can_be_cancelled():
                return Response(
                    {"error": "This payment cannot be cancelled"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Store subscription info before cancellation
            subscription_cancelled = (
                invoice.subscription and invoice.subscription.status == "pending"
            )

            # Cancel the invoice
            success = invoice.cancel()

            if success:
                response_message = "Payment cancelled successfully"
                if subscription_cancelled:
                    response_message += " and associated subscription cancelled"

                return Response(
                    {"message": response_message},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"error": "Failed to cancel payment"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except PaymentInvoice.DoesNotExist:
            return Response(
                {"error": "Payment invoice not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to cancel payment: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PaymentStatusView(APIView):
    """Check payment status and service health."""

    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get payment service status and user's pending payments."""
        try:
            # Get user's pending payment invoices
            pending_invoices = PaymentInvoice.objects.filter(
                profile=request.user.profile,
                status__in=["waiting", "confirming", "confirmed", "partially_paid"],
            )

            # Get service status
            try:
                balance = payment_service.get_account_balance()
                currencies = payment_service.get_supported_currencies()
                service_available = True
            except Exception:
                balance = None
                currencies = None
                service_available = False

            return Response(
                {
                    "service_available": service_available,
                    "pending_payments": PaymentInvoiceSerializer(
                        pending_invoices, many=True
                    ).data,
                    "supported_currencies": currencies,
                    "service_balance": balance,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": f"Status check failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
