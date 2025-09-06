from django.urls import path

from . import views

app_name = "user"

urlpatterns = [
    path(
        "auth/request-verification/",
        views.request_email_verification,
        name="request_email_verification",
    ),
    path("auth/verify-email/", views.verify_email_code, name="verify_email_code"),
    path("auth/register/", views.register_user, name="register_user"),
    path("auth/refresh/", views.refresh_token, name="refresh_token"),
    path("auth/token/refresh/", views.TokenRefreshView.as_view(), name="token_refresh"),
    path("profile/", views.user_profile, name="user_profile"),
    path("profile/detail/", views.profile_detail, name="profile_detail"),
]
