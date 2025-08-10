from django_filters import (CharFilter, DateTimeFromToRangeFilter, FilterSet,
                            NumberFilter)

from . import models


def filter_by_channel_ids(queryset, _name, value):
    """filter channels by id

    Args:
        queryset (queryset): queryset of channels
        name (_type_): _description_
        value (str): value of ids

    Returns:
        queryset: filtered queryset of channels
    """
    values = value.split(",")
    return queryset.filter(channel_id__in=values)


def filter_by_network_ids(queryset, _name, value):
    """filter networks by id

    Args:
        queryset (queryset): queryset of networks
        name (_type_): _description_
        value (str): value of ids

    Returns:
        queryset: filtered queryset of networks
    """
    values = value.split(",")
    return queryset.filter(channel__network_id__in=values)


def filter_by_tag_ids(queryset, _name, value):
    """filter tags by id

    Args:
        queryset (queryset): queryset of tags
        name (_type_): _description_
        value (str): value of ids

    Returns:
        queryset: filtered queryset of tags
    """
    values = value.split(",")
    return queryset.filter(channel__tags__in=values)


class PostFilter(FilterSet):
    date = DateTimeFromToRangeFilter(field_name="created_at")
    channels = CharFilter(method=filter_by_channel_ids)
    networks = CharFilter(method=filter_by_network_ids)
    tags = CharFilter(method=filter_by_tag_ids)
    max_id = NumberFilter(field_name="id", lookup_expr="lte")

    class Meta:
        model = models.Post
        fields = ("channels", "networks", "date", "tags")


def keyword_filter_by_channel_ids(queryset, _name, value):
    """filter keywords by channel ids

    Args:
        queryset (queryset): queryset of keywords
        name (_type_): _description_
        value (str): value of channel ids

    Returns:
        queryset: filtered queryset of keywords
    """
    values = value.split(",")
    return queryset.filter(post__channel_id__in=values)


def keyword_filter_by_network_ids(queryset, _name, value):
    """filter keywords by network ids

    Args:
        queryset (queryset): queryset of keywords
        name (_type_): _description_
        value (str): value of network ids

    Returns:
        queryset: filtered queryset of keywords
    """
    values = value.split(",")
    return queryset.filter(post__channel__network_id__in=values)


def keyword_filter_by_tag_ids(queryset, _name, value):
    """filter keywords by tag ids

    Args:
        queryset (queryset): queryset of keywords
        name (_type_): _description_
        value (str): value of tag ids

    Returns:
        queryset: filtered queryset of keywords
    """
    values = value.split(",")
    return queryset.filter(post__channel__tags__in=values)


class KeywordFilter(FilterSet):
    date = DateTimeFromToRangeFilter(field_name="created_at")
    channels = CharFilter(method=keyword_filter_by_channel_ids)
    networks = CharFilter(method=keyword_filter_by_network_ids)
    tags = CharFilter(method=keyword_filter_by_tag_ids)

    class Meta:
        model = models.Keyword
        fields = (
            "channels",
            "networks",
            "date",
            "tags",
        )


def channel_filter_by_network_ids(queryset, _name, value):
    """filter channels by network ids

    Args:
        queryset (queryset): queryset of keywords
        name (_type_): _description_
        value (str): value of network ids

    Returns:
        queryset: filtered queryset of keywords
    """
    values = value.split(",")
    return queryset.filter(network_id__in=values)


class ChannelFilter(FilterSet):
    date = DateTimeFromToRangeFilter(field_name="created_at")
    networks = CharFilter(method=channel_filter_by_network_ids)

    class Meta:
        model = models.Channel
        fields = (
            "status",
            "networks",
        )
