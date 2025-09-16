from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework_simplejwt.authentication import JWTAuthentication
from user.decorators import premium_required, track_feature_usage

from .models import CoverLetter
from .serializers import CoverLetterSerializer


class CoverLetterViewSet(ModelViewSet):
    """ViewSet for managing cover letters."""

    serializer_class = CoverLetterSerializer
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return cover letters for the authenticated user."""
        return CoverLetter.objects.filter(profile=self.request.user.profile).order_by(
            "-created_at"
        )

    def perform_create(self, serializer):
        """Create a new cover letter for the authenticated user."""
        serializer.save(profile=self.request.user.profile)

    @action(detail=False, methods=["post"], url_path="generate")
    @premium_required(feature_type="ai_cover_letter")
    def generate_cover_letter(self, request):
        """Generate AI cover letter - Premium feature only."""

        job_description = request.data.get("job_description")

        if not job_description:
            return Response(
                {"error": "Job description is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            profile = request.user.profile

            # Create cover letter instance
            cover_letter = CoverLetter.objects.create(
                profile=profile, job_description=job_description
            )

            # The post_save signal in the model will trigger the async task
            # to generate the cover letter content

            serializer = CoverLetterSerializer(cover_letter)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": f"Failed to generate cover letter: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def list(self, request, *args, **kwargs):
        """Get user's cover letters."""
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            return Response(
                {"error": f"Failed to retrieve cover letters: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def retrieve(self, request, *args, **kwargs):
        """Get specific cover letter details."""
        try:
            return super().retrieve(request, *args, **kwargs)
        except CoverLetter.DoesNotExist:
            return Response(
                {"error": "Cover letter not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to retrieve cover letter: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def destroy(self, request, *args, **kwargs):
        """Delete a cover letter."""
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return Response(
                {"message": "Cover letter deleted successfully"},
                status=status.HTTP_200_OK,
            )
        except CoverLetter.DoesNotExist:
            return Response(
                {"error": "Cover letter not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to delete cover letter: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
