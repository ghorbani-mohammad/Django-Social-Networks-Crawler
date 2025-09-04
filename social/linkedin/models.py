import logging

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from user.models import Profile

from reusable.models import BaseModel


logger = logging.getLogger(__name__)

class Keyword(BaseModel):
    name = models.CharField(max_length=20)
    words = models.TextField()
    image = models.FileField(
        upload_to="linkedin/keyword_images/", null=True, blank=True
    )

    @property
    def keywords_in_array(self):
        return [w.strip() for w in self.words.split(",")]

    def __str__(self):
        return f"({self.pk} - {self.name})"


class IgnoringFilterCategory(BaseModel):
    name = models.CharField(max_length=100)
    enable = models.BooleanField(default=True)

    def __str__(self):
        return f"({self.pk} - {self.name})"


class IgnoringFilter(BaseModel):
    TITLE = "title"
    COMPANY = "company"
    LOCATION = "location"
    PLACE_CHOICES = ((LOCATION, LOCATION), (TITLE, TITLE), (COMPANY, COMPANY))
    place = models.CharField(choices=PLACE_CHOICES, max_length=15)
    keyword = models.TextField(null=True)
    enable = models.BooleanField(default=True)
    category = models.ForeignKey(
        IgnoringFilterCategory, on_delete=models.CASCADE, null=True, blank=True
    )

    def save(self, *args, **kwargs):
        if self.keyword:
            self.keyword = self.keyword.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"({self.pk} - {self.place} - {self.keyword})"


class JobSearch(BaseModel):
    url = models.URLField()
    name = models.CharField(max_length=100)
    enable = models.BooleanField(default=True)
    message = models.TextField(null=True, blank=True)
    last_crawl_at = models.DateTimeField(null=True, blank=True)
    last_crawl_count = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="how many items was found"
    )
    keywords = models.ManyToManyField(Keyword, blank=True)
    ignore_filters = models.ManyToManyField(IgnoringFilter, blank=True)
    just_easily_apply = models.BooleanField(default=False)
    output_channel = models.ForeignKey(
        "notification.Channel",
        on_delete=models.SET_NULL,
        null=True,
        related_name="linkedin_pages",
    )
    page_count = models.PositiveSmallIntegerField(
        help_text="how many pages should be crawled", default=1, blank=True
    )
    priority = models.PositiveSmallIntegerField(
        help_text="pages with higher priority, will be at the first of crawl queue",
        blank=True,
        default=0,
    )
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="job_search",
        null=True,
        blank=True,
    )

    @property
    def keywords_in_array(self):
        result = []
        for keyword in self.keywords.all():
            result = result + keyword.keywords_in_array
        return result

    @property
    def page_data(self):
        return (
            self.message,
            self.url,
            self.output_channel.pk,
            self.keywords_in_array,
            self.ignore_filters.filter(enable=True),
            self.just_easily_apply,
        )

    @property
    def ignoring_filters_count(self):
        return self.ignore_filters.count()

    def __str__(self):
        return f"({self.pk} - {self.name})"


class IgnoredJob(BaseModel):
    url = models.URLField(null=True)
    description = models.TextField(null=True)
    title = models.CharField(max_length=300, null=True)
    company = models.CharField(max_length=100, null=True)
    location = models.CharField(max_length=200, null=True)
    language = models.CharField(max_length=40, null=True)
    reason = models.CharField(max_length=100, null=True, blank=True)


class ExpressionSearch(BaseModel):
    url = models.URLField()
    name = models.CharField(max_length=100)
    enable = models.BooleanField(default=True)
    last_crawl_at = models.DateTimeField(null=True, blank=True)
    output_channel = models.ForeignKey(
        "notification.Channel",
        on_delete=models.SET_NULL,
        null=True,
        related_name="linkedin_expression_searches",
    )
    ignore_categories = models.ManyToManyField(IgnoringFilterCategory, blank=True)


class Job(BaseModel):
    """Stores all crawled LinkedIn jobs regardless of eligibility."""

    # A stable id we read from the job card, used for upserts/deduplication
    network_id = models.CharField(max_length=100, unique=True, null=True, blank=True)

    # Basic job fields
    url = models.URLField(null=True, blank=True)
    title = models.CharField(max_length=300, null=True, blank=True)
    company = models.CharField(max_length=100, null=True, blank=True)
    location = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    language = models.CharField(max_length=40, null=True, blank=True)

    # Extra metadata
    company_size = models.CharField(max_length=100, null=True, blank=True)
    easy_apply = models.BooleanField(default=False)

    # Crawl context and decision
    page = models.ForeignKey(
        JobSearch, on_delete=models.SET_NULL, null=True, blank=True, related_name="jobs"
    )
    eligible = models.BooleanField(default=True)
    rejected_reason = models.CharField(max_length=100, null=True, blank=True)

    # Matched keywords for this job based on content
    matched_keywords = models.ManyToManyField(Keyword, blank=True)

    # Keywords actually found in the job description (comma-separated string)
    found_keywords = models.TextField(
        null=True,
        blank=True,
        help_text="Keywords found in job description, comma-separated",
    )

    def __str__(self):
        return f"({self.pk} - {self.title})"


class IgnoredAccount(BaseModel):
    job_search = models.ManyToManyField(JobSearch, blank=True)
    expression_search = models.ManyToManyField(ExpressionSearch, blank=True)
    account_name = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"({self.pk} - {self.account_name})"


@receiver(post_save, sender=Job)
def job_post_save(sender, instance, created, **kwargs):
    """Send notification when a new eligible job is created."""
    if not (created and instance.eligible and instance.page):
        return

    # Import here to avoid circular imports
    from . import tasks

    # Prepare job data for notification
    job_data = {
        "id": instance.pk,
        "network_id": instance.network_id,
        "url": instance.url,
        "title": instance.title,
        "company": instance.company,
        "location": instance.location,
        "description": instance.description,
        "language": instance.language,
        "company_size": instance.company_size,
        "easy_apply": "✅" if instance.easy_apply else "❌",
    }

    # Get page data for notification
    page = instance.page
    message = page.message
    keywords = page.keywords_in_array
    output_channel_pk = page.output_channel.pk if page.output_channel else None
    cover_letter = ""  # Can be enhanced later if needed

    if output_channel_pk:
        # Send notification asynchronously
        tasks.send_notification(
            message, job_data, keywords, output_channel_pk, cover_letter
        )

    # Also send WebSocket notification for real-time updates
    try:
        tasks.send_websocket_notification(job_data)
    except Exception as e:
        logger.error(f"Failed to send WebSocket notification: {str(e)}")
