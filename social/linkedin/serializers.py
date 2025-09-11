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
    found_keywords = serializers.CharField(read_only=True)
    found_keywords_as_hashtags = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    keywords_as_hashtags = serializers.SerializerMethodField()

    class Meta:
        model = models.Job
        fields = (
            "id",
            "url",
            "title",
            "company",
            "source",
            "found_keywords",
            "found_keywords_as_hashtags",
            "keywords_as_hashtags",
            "image",
            "created_at",
            "updated_at",
            "description",
        )

    def get_image(self, obj: models.Job):
        # Try to get image from found keywords first, then fall back to matched keywords
        if obj.found_keywords:
            # Parse found keywords to find matching keyword objects
            found_keywords_list = [
                kw.strip() for kw in obj.found_keywords.split(",") if kw.strip()
            ]
            for found_kw in found_keywords_list:
                # Find keyword object that contains this found keyword
                for keyword in obj.matched_keywords.all():
                    if found_kw in keyword.keywords_in_array:
                        if keyword.image:
                            url = getattr(keyword.image, "url", None)
                            if url:
                                request = (
                                    self.context.get("request")
                                    if hasattr(self, "context")
                                    else None
                                )
                                if request is not None:
                                    # Force HTTPS scheme for image URLs
                                    absolute_uri = request.build_absolute_uri(url)
                                    if absolute_uri.startswith("http://"):
                                        return absolute_uri.replace("http://", "https://", 1)
                                    return absolute_uri
                                return url
        return None

    def get_keywords_as_hashtags(self, obj: models.Job):
        """Return matched keywords as hashtag strings for easy frontend display."""
        hashtags = []
        for keyword in obj.matched_keywords.all():
            if keyword.words:
                # Split the words and add hashtag prefix
                words = [w.strip() for w in keyword.words.split(",") if w.strip()]
                hashtags.extend([f"#{word}" for word in words])
        return hashtags

    def get_found_keywords_as_hashtags(self, obj: models.Job):
        """Return found keywords as hashtag strings for easy frontend display."""
        if not obj.found_keywords:
            return []

        found_keywords_list = [
            kw.strip() for kw in obj.found_keywords.split(",") if kw.strip()
        ]
        return [f"#{keyword}" for keyword in found_keywords_list]


class FavoriteJobSerializer(serializers.ModelSerializer):
    job = JobSerializer(read_only=True)
    job_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = models.FavoriteJob
        fields = (
            "id",
            "job",
            "job_id",
            "created_at",
        )
        read_only_fields = ("id", "created_at", "profile")
