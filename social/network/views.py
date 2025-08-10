import logging

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as rf_filters
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from . import filters, models, serializers, utils

logger = logging.getLogger(__name__)


class ListPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"


class NetworkViewSet(ModelViewSet):
    queryset = models.Network.objects.order_by("-id")
    serializer_class = serializers.NetworkSerializer
    pagination_class = ListPagination
    filter_backends = [
        rf_filters.SearchFilter,
        DjangoFilterBackend,
        rf_filters.OrderingFilter,
    ]
    search_fields = ["name"]
    ordering_fields = ["name"]
    filterset_fields = ["status"]


class TagViewSet(ModelViewSet):
    queryset = models.Tag.objects.order_by("-id")
    serializer_class = serializers.TagSerializer
    pagination_class = ListPagination
    search_fields = ["name"]
    ordering_fields = ["name"]
    filter_backends = [rf_filters.SearchFilter, rf_filters.OrderingFilter]


class ChannelViewSet(ModelViewSet):
    queryset = models.Channel.objects.order_by("-id")
    serializer_class = serializers.ChannelSerializer
    pagination_class = ListPagination
    filter_backends = [
        DjangoFilterBackend,
        rf_filters.SearchFilter,
        rf_filters.OrderingFilter,
    ]
    search_fields = ["username"]
    ordering_fields = ["username"]
    filterset_class = filters.ChannelFilter


class PostViewSet(ModelViewSet):
    queryset = models.Post.objects.order_by("-id")
    serializer_class = serializers.PostSerializer
    pagination_class = ListPagination
    filter_backends = [
        DjangoFilterBackend,
        rf_filters.SearchFilter,
        rf_filters.OrderingFilter,
    ]
    search_fields = ["body"]
    ordering_fields = ["views_count", "share_count"]
    filterset_fields = ["channel", "channel__network"]


class PostCountAPIView(ListAPIView):
    queryset = models.Post.objects.order_by("-id")
    serializer_class = serializers.PostSerializer
    pagination_class = ListPagination
    filterset_class = filters.PostFilter
    filter_backends = [DjangoFilterBackend]

    def list(self, request, *_args, **_kwargs):
        serializer = serializers.PostCountInputSerializer(data=request.GET)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        response = super().list(request)
        qs = self.filter_queryset(self.get_queryset())
        search_excluded_qs = utils.get_search_excluded_qs(self)
        response.data["statics"] = utils.get_count_statics(
            qs,
            search_excluded_qs,
            data["type"],
            data["date_after"],
            data["date_before"],
        )
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        response.data["today_posts"] = (
            self.get_queryset().filter(created_at__gte=today).count()
        )
        response.data["channel_posts"] = (
            (models.Channel.objects.get(pk=request.GET["channel"]).today_posts_count)
            if "channel" in request.GET
            else self.get_queryset().count()
        )
        response.data["network_posts"] = (
            (
                models.Network.objects.get(
                    pk=request.GET["channel__network"]
                ).today_posts_count
            )
            if "channel__network" in request.GET
            else self.get_queryset().count()
        )
        return response


class SearchCountAPIView(ListAPIView):
    serializer_class = serializers.PostSerializer
    pagination_class = ListPagination
    filter_backends = [rf_filters.SearchFilter, DjangoFilterBackend]
    filterset_class = filters.PostFilter
    search_fields = ["body"]

    def filter_queryset(self, queryset):
        operator = self.request.GET["operator"]
        return utils.get_search_modified_qs(self, queryset, operator)

    def get_queryset(self):
        return models.Post.objects.order_by("-id")

    def list(self, request, *_args, **_kwargs):
        serializer = serializers.PostCountInputSerializer(data=request.GET)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        response = super().list(request)
        qs = self.filter_queryset(self.get_queryset())
        search_excluded_qs = utils.get_search_excluded_qs(self)
        response.data["statics"] = utils.get_count_statics(
            qs,
            search_excluded_qs,
            data["type"],
            data["date_after"],
            data["date_before"],
        )
        response.data["keyword_statics"] = utils.get_keyword_statics(
            models.Keyword.objects.filter(post__in=qs),
            data["type"],
            data["date_after"],
            data["date_before"],
        )
        temp = utils.get_channels_statistics(qs)
        temp["all_enabled_channels_count"] = models.Channel.objects.filter(
            status=True
        ).count()
        temp["channels_not_talked_about_term_count"] = (
            temp["all_enabled_channels_count"]
            - temp["channels_talked_about_term_count"]
        )
        response.data["channels_statistics"] = temp
        return response


class KeywordAPIView(ListAPIView):
    queryset = models.Keyword.objects.filter(ignored=False).order_by("-id")
    serializer_class = serializers.KeywordSerializer
    pagination_class = ListPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.KeywordFilter

    def list(self, request, *_args, **_kwargs):
        serializer = serializers.PostCountInputSerializer(data=request.GET)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        response = super().list(request)
        queryset = self.filter_queryset(self.get_queryset())
        response.data["statics"] = utils.get_keyword_statics(
            queryset, data["type"], data["date_after"], data["date_before"]
        )
        return response


class BackupViewSet(ModelViewSet):
    queryset = models.Backup.objects.order_by("-id")
    serializer_class = serializers.BackupSerializer
    pagination_class = ListPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["type", "status"]


class TestErrorView(APIView):
    def get(self, _request):
        logger.error("Logger error executed for test purposes!")
        raise Exception("Exception executed for test purposes!")
