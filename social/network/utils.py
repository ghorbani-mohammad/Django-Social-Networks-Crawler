from functools import reduce
from operator import and_, or_

from dateutil.relativedelta import relativedelta
from django.db.models import Count, Q
from django.db.models.functions import TruncDate, TruncHour, TruncMonth
from django.utils import timezone
from network.models import Channel, Network

KEYWORD_NUMBER = 20
CATEGORY_NUMBER = 5
CHANNEL_NUMBER = 5


def get_search_modified_qs(apiview, queryset, operator):
    for backend in list(apiview.filter_backends):
        if backend.__name__ != "SearchFilter":
            queryset = backend().filter_queryset(apiview.request, queryset, apiview)
        else:
            if "search" in apiview.request.GET:
                words = apiview.request.GET["search"].split(",")
                words = [word for word in words if len(word) > 1]
                if operator == "and":
                    queryset = queryset.filter(
                        reduce(and_, [Q(body__contains=word) for word in words])
                    )
                elif operator == "or":
                    queryset = queryset.filter(
                        reduce(or_, [Q(body__contains=word) for word in words])
                    )
    return queryset


def get_search_excluded_qs(apiview):
    queryset = apiview.get_queryset()
    for backend in list(apiview.filter_backends):
        if backend.__name__ != "SearchFilter":
            queryset = backend().filter_queryset(apiview.request, queryset, apiview)
    return queryset


def hourly_iterate(start, finish):
    result = []
    start = start.replace(minute=0, second=0, microsecond=0)
    while start <= finish:
        result.append(start)
        start += timezone.timedelta(hours=1)
    return result


def daily_iterate(start, finish):
    result = []
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while start <= finish:
        result.append(start)
        start += timezone.timedelta(days=1)
    return result


def monthly_iterate(start, finish):
    result = []
    start = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    while start <= finish:
        result.append(start)
        start += relativedelta(months=1)
    return result


def category_statics(cat_query):
    cat_query = (
        cat_query.values("main_category_title")
        .annotate(count=Count("main_category_title"))
        .order_by("-count")
    )
    categories = []
    categories_posts = 0
    for category in cat_query[: min(CATEGORY_NUMBER, len(cat_query))]:
        categories.append(
            {
                "category": category["main_category_title"],
                "count": category["count"],
            }
        )
        categories_posts += category["count"]
    return categories_posts, categories


def get_hourly_statics(queryset, search_excluded_qs, start, end):
    result = []
    end = end or (start - timezone.timedelta(hours=12))
    queryset = queryset.filter(created_at__gte=start, created_at__lte=end)
    s_e_qs = search_excluded_qs.filter(created_at__gte=start, created_at__lte=end)
    queryset = (
        queryset.annotate(hour=TruncHour("created_at"))
        .values("hour")
        .annotate(count=Count("id"))
        .order_by("hour")
    )
    s_e_qs = s_e_qs.annotate(hour=TruncHour("created_at"))
    for hour in hourly_iterate(start, end):
        count = queryset.filter(hour__hour=hour.hour, hour__day=hour.day).first()
        count = count["count"] if count else 0
        total_count = s_e_qs.filter(hour__hour=hour.hour, hour__day=hour.day).count()
        temp_result = {"hour": hour, "count": count, "total_count": total_count}
        cat_query = queryset.filter(hour__hour=hour.hour, hour__day=hour.day)
        (
            temp_result["categories_posts"],
            temp_result["categories"],
        ) = category_statics(cat_query)
        networks = {}
        for network in Network.objects.all():
            networks[network.name] = s_e_qs.filter(
                hour__hour=hour.hour, hour__day=hour.day, channel__network=network
            ).count()
        temp_result["networks"] = networks
        channels = {}
        for channel in Channel.objects.all():
            channels[channel.name] = s_e_qs.filter(
                hour__hour=hour.hour, hour__day=hour.day, channel=channel
            ).count()
        temp_result["channels"] = channels
        result.append(temp_result)
    return result


def get_daily_statics(queryset, search_excluded_qs, start, end):
    result = []
    end = end or (start - timezone.timedelta(days=7))
    queryset = queryset.filter(created_at__gte=start, created_at__lte=end)
    s_e_qs = search_excluded_qs.filter(created_at__gte=start, created_at__lte=end)
    queryset = (
        queryset.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    s_e_qs = s_e_qs.annotate(day=TruncDate("created_at"))
    for day in daily_iterate(start, end):
        count = queryset.filter(day__month=day.month, day__day=day.day).first()
        count = count["count"] if count else 0
        total_count = s_e_qs.filter(day__month=day.month, day__day=day.day).count()
        temp_result = {"day": day, "count": count, "total_count": total_count}
        cat_query = queryset.filter(day__month=day.month, day__day=day.day)
        (
            temp_result["categories_posts"],
            temp_result["categories"],
        ) = category_statics(cat_query)
        for network in Network.objects.all():
            temp_result[network.name] = s_e_qs.filter(
                day__month=day.month, day__day=day.day, channel__network=network
            ).count()
        result.append(temp_result)
    return result


def get_monthly_statics(queryset, search_excluded_qs, start, end):
    result = []
    end = end or (start - relativedelta(months=7))
    queryset = queryset.filter(created_at__gte=start, created_at__lte=end)
    s_e_qs = search_excluded_qs.filter(created_at__gte=start, created_at__lte=end)
    queryset = (
        queryset.annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    s_e_qs = s_e_qs.annotate(month=TruncMonth("created_at"))
    for month in monthly_iterate(start, end):
        count = queryset.filter(
            month__year=month.year, month__month=month.month
        ).first()
        count = count["count"] if count else 0
        total_count = s_e_qs.filter(
            month__year=month.year, month__month=month.month
        ).count()
        temp_result = {"month": month, "count": count, "total_count": total_count}
        cat_query = queryset.filter(month__year=month.year, month__month=month.month)
        (
            temp_result["categories_posts"],
            temp_result["categories"],
        ) = category_statics(cat_query)
        for network in Network.objects.all():
            temp_result[network.name] = s_e_qs.filter(
                month__year=month.year,
                month__month=month.month,
                channel__network=network,
            ).count()
        result.append(temp_result)
    return result


def get_count_statics(queryset, search_excluded_qs, interval, start=None, end=None):
    result = []
    if interval == "hourly":
        result = get_hourly_statics(queryset, search_excluded_qs, start, end)
    elif interval == "daily":
        result = get_daily_statics(queryset, search_excluded_qs, start, end)
    elif interval == "monthly":
        result = get_monthly_statics(queryset, search_excluded_qs, start, end)
    return result


def get_keyword_statics(queryset, interval, start=None, end=None):
    result = []
    if interval == "hourly":
        start = start or timezone.localtime()
        end = end or (start - timezone.timedelta(hours=12))
        queryset = queryset.filter(created_at__gte=start, created_at__lte=end).annotate(
            hour=TruncHour("created_at")
        )
        for hour in hourly_iterate(start, end):
            temp = queryset.filter(hour__hour=hour.hour, hour__day=hour.day)
            temp = (
                temp.values("keyword")
                .annotate(count=Count("keyword"))
                .order_by("-count")
            )
            keywords = []
            for keyword in temp[: min(KEYWORD_NUMBER, len(temp))]:
                keywords.append(
                    {"keyword": keyword["keyword"], "count": keyword["count"]}
                )
            result.append(
                {
                    "hour": hour,
                    "keywords": keywords,
                }
            )
    elif interval == "daily":
        start = start or timezone.localtime()
        end = end or (start - timezone.timedelta(days=7))
        queryset = queryset.filter(created_at__gte=start, created_at__lte=end).annotate(
            day=TruncDate("created_at")
        )
        for day in daily_iterate(start, end):
            temp = queryset.filter(day__month=day.month, day__day=day.day)
            temp = (
                temp.values("keyword")
                .annotate(count=Count("keyword"))
                .order_by("-count")
            )
            keywords = []
            for keyword in temp[: min(KEYWORD_NUMBER, len(temp))]:
                keywords.append(
                    {"keyword": keyword["keyword"], "count": keyword["count"]}
                )
            result.append(
                {
                    "day": day,
                    "keywords": keywords,
                }
            )
    elif interval == "monthly":
        start = start or timezone.localtime()
        end = end or (start - relativedelta(months=7))
        queryset = queryset.filter(created_at__gte=start, created_at__lte=end).annotate(
            month=TruncMonth("created_at")
        )
        for month in monthly_iterate(start, end):
            temp = queryset.filter(month__year=month.year, month__month=month.month)
            temp = (
                temp.values("keyword")
                .annotate(count=Count("keyword"))
                .order_by("-count")
            )
            keywords = []
            for keyword in temp[: min(KEYWORD_NUMBER, len(temp))]:
                keywords.append(
                    {"keyword": keyword["keyword"], "count": keyword["count"]}
                )
            result.append(
                {
                    "month": month,
                    "keywords": keywords,
                }
            )
    return result


def get_channels_statistics(queryset):
    total = 0
    channels = (
        queryset.values("channel", "channel__name")
        .annotate(count=Count("channel"))
        .order_by("-count")
    )
    channels_talked_about_term_count = len(channels)
    channels = channels[: min(CHANNEL_NUMBER, len(channels))]
    channels = [
        {"channel": channel["channel__name"], "count": channel["count"]}
        for channel in channels
    ]
    for channel in channels:
        total += channel["count"]
    return {
        "channels": channels,
        "total": total,
        "channels_talked_about_term_count": channels_talked_about_term_count,
    }
