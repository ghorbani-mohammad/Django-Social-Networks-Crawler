from rest_framework import serializers

from .models import CoverLetter


class CoverLetterSerializer(serializers.ModelSerializer):
    """Serializer for CoverLetter model."""

    profile_id = serializers.IntegerField(source="profile.id", read_only=True)
    is_generated = serializers.SerializerMethodField()

    class Meta:
        model = CoverLetter
        fields = [
            "id",
            "cover_letter",
            "job_description",
            "profile_id",
            "is_generated",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "profile", "created_at", "updated_at"]

    def get_is_generated(self, obj):
        """Check if cover letter content has been generated."""
        return bool(obj.cover_letter and obj.cover_letter.strip())
