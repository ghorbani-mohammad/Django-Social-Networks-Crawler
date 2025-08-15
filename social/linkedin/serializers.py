from rest_framework import serializers

from . import models


class IgnoredJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.IgnoredJob
        fields = (
            "id",
            "url",
            "title",
            "company",
            "location",
            "language",
            "reason",
            "description",
            "created_at",
            "updated_at",
        )


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Job
        fields = (
            "id",
            "url",
            "title",
            "company",
        )
