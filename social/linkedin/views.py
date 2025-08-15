from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as rf_filters
from rest_framework.viewsets import ReadOnlyModelViewSet

from .models import IgnoredJob, Job
from .permissions import HasPublicAPIKey
from .serializers import IgnoredJobSerializer, JobSerializer


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
    search_fields = ["title", "company", "location", "description"]
    ordering_fields = ["created_at", "updated_at"]
    filterset_fields = ["language", "company", "location", "reason"]
