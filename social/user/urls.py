from django.urls import path

from . import views

app_name = "user"

urlpatterns = [
    path(
        "auth/request-verification/",
        views.RequestEmailVerificationView.as_view(),
        name="request_email_verification",
    ),
    path(
        "auth/verify-email/",
        views.VerifyEmailCodeView.as_view(),
        name="verify_email_code",
    ),
    path("auth/register/", views.RegisterUserView.as_view(), name="register_user"),
    path("auth/refresh/", views.RefreshTokenView.as_view(), name="refresh_token"),
    path("auth/token/refresh/", views.TokenRefreshView.as_view(), name="token_refresh"),
    path("profile/", views.UserProfileView.as_view(), name="user_profile"),
    path("profile/detail/", views.ProfileDetailView.as_view(), name="profile_detail"),
    # Subscription endpoints
    path(
        "subscriptions/plans/",
        views.SubscriptionPlansView.as_view(),
        name="subscription_plans",
    ),
    path(
        "subscriptions/",
        views.UserSubscriptionsView.as_view(),
        name="user_subscriptions",
    ),
    path(
        "subscriptions/current/",
        views.CurrentSubscriptionView.as_view(),
        name="current_subscription",
    ),
    path(
        "subscriptions/<int:subscription_id>/cancel/",
        views.CancelSubscriptionView.as_view(),
        name="cancel_subscription",
    ),
    path("feature-usage/", views.FeatureUsageView.as_view(), name="feature_usage"),
    path("premium-status/", views.PremiumStatusView.as_view(), name="premium_status"),
    # Payment endpoints
    path(
        "payments/invoices/",
        views.PaymentInvoicesView.as_view(),
        name="payment_invoices",
    ),
    path(
        "payments/invoices/<int:invoice_id>/",
        views.PaymentInvoiceDetailView.as_view(),
        name="payment_invoice_detail",
    ),
    path(
        "payments/invoices/<int:invoice_id>/cancel/",
        views.CancelPaymentInvoiceView.as_view(),
        name="cancel_payment_invoice",
    ),
    path(
        "payments/webhook/", views.PaymentWebhookView.as_view(), name="payment_webhook"
    ),
    path("payments/status/", views.PaymentStatusView.as_view(), name="payment_status"),
]
