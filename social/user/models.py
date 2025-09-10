import secrets
from datetime import timedelta

from django.db import models
from django.utils import timezone

from reusable.models import BaseModel


class Profile(BaseModel):
    user = models.OneToOneField("auth.User", on_delete=models.CASCADE)
    cell_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    chat_id = models.CharField(max_length=15, unique=True, null=True, blank=True)
    about_me = models.TextField(null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    additional_notes = models.TextField(null=True, blank=True)
    education_background = models.TextField(null=True, blank=True)
    professional_experience = models.TextField(null=True, blank=True)

    # Email verification fields
    verification_code = models.CharField(max_length=6, null=True, blank=True)
    verification_expires_at = models.DateTimeField(null=True, blank=True)
    verification_attempts = models.IntegerField(default=0)
    is_email_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"({self.pk} - {self.cell_number or self.user.email})"

    def save(self, *args, **kwargs):
        if not self.verification_code and not self.is_email_verified:
            self.verification_code = self.generate_verification_code()
        if not self.verification_expires_at and not self.is_email_verified:
            self.verification_expires_at = timezone.now() + timedelta(minutes=10)
        super().save(*args, **kwargs)

    @staticmethod
    def generate_verification_code():
        return str(secrets.randbelow(900000) + 100000)

    def is_verification_expired(self):
        if not self.verification_expires_at:
            return True
        return timezone.now() > self.verification_expires_at

    def can_attempt_verification(self):
        max_attempts = 3
        return (
            self.verification_attempts < max_attempts
            and not self.is_verification_expired()
        )

    def increment_verification_attempts(self):
        self.verification_attempts += 1
        self.save(update_fields=["verification_attempts"])

    def mark_email_as_verified(self):
        self.is_email_verified = True
        self.verification_code = None
        self.verification_expires_at = None
        self.verification_attempts = 0
        self.save(
            update_fields=[
                "is_email_verified",
                "verification_code",
                "verification_expires_at",
                "verification_attempts",
            ]
        )

    def reset_verification_code(self):
        self.verification_code = self.generate_verification_code()
        self.verification_expires_at = timezone.now() + timedelta(minutes=10)
        self.verification_attempts = 0
        self.save(
            update_fields=[
                "verification_code",
                "verification_expires_at",
                "verification_attempts",
            ]
        )

    def add_favorite_job(self, job):
        """Add a job to user's favorites."""
        from linkedin.models import FavoriteJob

        favorite, created = FavoriteJob.objects.get_or_create(profile=self, job=job)
        return favorite, created

    def remove_favorite_job(self, job):
        """Remove a job from user's favorites."""
        from linkedin.models import FavoriteJob

        try:
            favorite = FavoriteJob.objects.get(profile=self, job=job)
            favorite.delete()
            return True
        except FavoriteJob.DoesNotExist:
            return False

    def is_job_favorite(self, job):
        """Check if a job is in user's favorites."""
        from linkedin.models import FavoriteJob

        return FavoriteJob.objects.filter(profile=self, job=job).exists()

    def get_favorite_jobs(self):
        """Get all favorite jobs for this user."""
        from linkedin.models import Job

        return Job.objects.filter(favorited_by__profile=self).order_by("-created_at")
