from celery import shared_task
from celery.utils.log import get_task_logger

from . import models
from .chatgpt.main import get_cover_letter

logger = get_task_logger(__name__)


@shared_task
def create_cover_letter(cover_letter_id: int):
    logger.info(f"create_cover_letter({cover_letter_id})")
    cover_letter = models.CoverLetter.objects.get(pk=cover_letter_id)
    cover_letter.cover_letter = get_cover_letter(
        cover_letter.profile.about_me, cover_letter.job_description
    )
    cover_letter.save()
