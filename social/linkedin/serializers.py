from rest_framework import serializers

from . import models


class KeywordSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Keyword
        fields = (
            "id",
            "name",
            "image",
        )


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
    matched_keywords = KeywordSerializer(many=True, read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = models.Job
        fields = (
            "id",
            "url",
            "title",
            "company",
            "matched_keywords",
            "image",
        )

    def get_image(self, obj: models.Job):
        for kw in obj.matched_keywords.all():
            if kw.image:
                url = getattr(kw.image, "url", None)
                if url:
                    return url
        return None
