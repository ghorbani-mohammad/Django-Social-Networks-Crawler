from functools import wraps

from rest_framework import status
from rest_framework.response import Response


def premium_required(feature_type=None):
    """
    Decorator to require premium subscription for accessing certain features.

    Args:
        feature_type: Type of feature being accessed (for usage tracking)
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not hasattr(request.user, "profile"):
                return Response(
                    {"error": "User profile not found"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            profile = request.user.profile

            if not profile.has_active_premium_subscription():
                return Response(
                    {
                        "error": "Premium subscription required",
                        "message": "This feature requires an active premium subscription. Please upgrade your account.",
                        "upgrade_url": "/api/v1/user/subscriptions/plans/",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Track feature usage if feature_type is provided
            if feature_type:
                from .models import FeatureUsage

                usage, created = FeatureUsage.objects.get_or_create(
                    profile=profile,
                    feature_type=feature_type,
                    defaults={"usage_count": 0},
                )
                usage.increment_usage()

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def check_premium_access(user):
    """
    Helper function to check if user has premium access.

    Args:
        user: Django User instance

    Returns:
        bool: True if user has premium access, False otherwise
    """
    if not hasattr(user, "profile"):
        return False

    return user.profile.has_active_premium_subscription()


def track_feature_usage(profile, feature_type, metadata=None):
    """
    Helper function to track premium feature usage.

    Args:
        profile: User Profile instance
        feature_type: Type of feature being used
        metadata: Optional metadata dictionary
    """
    from .models import FeatureUsage

    usage, created = FeatureUsage.objects.get_or_create(
        profile=profile, feature_type=feature_type, defaults={"usage_count": 0}
    )
    usage.increment_usage(metadata)
    return usage
