from rest_framework import serializers

from . import models


class KeywordSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Keyword
        fields = (
            "id",
            "name",
            "words",
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
    keywords_as_hashtags = serializers.SerializerMethodField()

    class Meta:
        model = models.Job
        fields = (
            "id",
            "url",
            "title",
            "company",
            "matched_keywords",
            "keywords_as_hashtags",
            "image",
            "created_at",
            "updated_at",
            "description",
        )

    def get_image(self, obj: models.Job):
        for kw in obj.matched_keywords.all():
            if kw.image:
                url = getattr(kw.image, "url", None)
                if url:
                    request = (
                        self.context.get("request")
                        if hasattr(self, "context")
                        else None
                    )
                    if request is not None:
                        return request.build_absolute_uri(url)
                    return url
        return None

    def get_keywords_as_hashtags(self, obj: models.Job):
        """Return keywords as hashtag strings for easy frontend display."""
        hashtags = []
        for keyword in obj.matched_keywords.all():
            if keyword.words:
                # Split the words and add hashtag prefix
                words = [w.strip() for w in keyword.words.split(",") if w.strip()]
                hashtags.extend([f"#{word}" for word in words])
        return hashtags
