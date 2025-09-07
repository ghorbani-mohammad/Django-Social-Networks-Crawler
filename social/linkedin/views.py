from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as rf_filters
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import FavoriteJob, IgnoredJob, Job
from .permissions import HasPublicAPIKey
from .serializers import (FavoriteJobSerializer, IgnoredJobSerializer,
                          JobSerializer)


class IgnoredJobViewSet(ReadOnlyModelViewSet):
    queryset = IgnoredJob.objects.order_by("-id")
    serializer_class = IgnoredJobSerializer
    permission_classes = [HasPublicAPIKey]
    filter_backends = [
        DjangoFilterBackend,
        rf_filters.SearchFilter,
        rf_filters.OrderingFilter,
    ]
    search_fields = [
        "title",
        "company",
        "location",
        "language",
        "reason",
        "description",
    ]
    ordering_fields = ["created_at", "updated_at"]
    filterset_fields = ["language", "company", "location", "reason"]


class JobViewSet(ReadOnlyModelViewSet):
    queryset = Job.objects.order_by("-id")
    serializer_class = JobSerializer
    permission_classes = [HasPublicAPIKey]
    filter_backends = [
        DjangoFilterBackend,
        rf_filters.SearchFilter,
        rf_filters.OrderingFilter,
    ]
    search_fields = [
        "title",
        "company",
        "location",
        "description",
        "found_keywords",
    ]
    ordering_fields = ["created_at", "updated_at"]
    filterset_fields = [
        "language",
        "company",
        "location",
        "rejected_reason",
    ]


# Favorites API Endpoint - Simple ModelViewSet
class FavoriteJobViewSet(ModelViewSet):
    """Simple ModelViewSet for managing user's favorite jobs - Create, Retrieve, Delete only."""

    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = FavoriteJobSerializer

    def get_queryset(self):
        """Get favorites for the authenticated user."""
        try:
            profile = self.request.user.profile
            return FavoriteJob.objects.filter(profile=profile).select_related("job")
        except:
            return FavoriteJob.objects.none()

    def perform_create(self, serializer):
        """Override create to handle profile assignment."""
        try:
            profile = self.request.user.profile
        except:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"error": "User profile not found"})

        # Get job_id from request data
        job_id = self.request.data.get("job_id")
        if not job_id:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"job_id": "This field is required"})

        try:
            job = Job.objects.get(id=job_id)
        except Job.DoesNotExist:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"job_id": "Job not found"})

        # Check if already favorited
        if FavoriteJob.objects.filter(profile=profile, job=job).exists():
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"job_id": "Job is already in favorites"})

        serializer.save(profile=profile, job=job)
