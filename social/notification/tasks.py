import traceback

from celery import shared_task
from celery.utils.log import get_task_logger

from . import models, utils

logger = get_task_logger(__name__)


@shared_task()
def send_telegram_message(message):
    """This function gets a string message and sends it to all defined accounts.

    Args:
        message (str): text message

    Raises:
        Exception: if sending message was not successful.
    """
    bot = models.TelegramBot.objects.last()
    accounts = models.TelegramAccount.objects.all()
    for account in accounts:
        resp = utils.telegram_bot_send_text(
            bot.telegram_token, account.chat_id, message
        )
        if not resp["ok"]:
            logger.error("%s\n\n%s", traceback.format_exc(), resp["description"])


@shared_task()
def send_message_to_telegram_channel(message, channel_pk):
    """This function gets a string message and sends it to specific channel.

    Args:
        message (str): text message
        channel_pk (int): id of destination channel (Channel)

    Raises:
        Exception: if sending message was not successful.
    """
    from notification.models import Channel

    bot = models.TelegramBot.objects.last()
    channel_output = Channel.objects.get(pk=channel_pk)
    resp = utils.telegram_bot_send_text(
        bot.telegram_token, channel_output.username, message
    )
    if not resp["ok"]:
        logger.error(
            "%s\n\nmessage was: %s\n\n%s",
            traceback.format_exc(),
            message,
            resp["description"],
        )
