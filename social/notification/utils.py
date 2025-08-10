import requests
import html
import json


def limit_words(text: str, max_words: int = 100) -> str:
    words = text.split()
    return text if len(words) <= max_words else " ".join(words[:max_words]) + " ..."


def html_link(url: str, text: str) -> str:
    safe_href = html.escape(url, quote=True)
    safe_text = html.escape(text, quote=False)
    return f'<a href="{safe_href}">{safe_text}</a>'


def telegram_text_purify(text: str):
    return text.replace("#", "-").replace("&", "-")


def telegram_bot_send_text(token, chat_id, message):
    send_text = (
        "https://api.telegram.org/bot"
        + token
        + "/sendMessage?chat_id="
        + chat_id
        + "&text="
        + message
        + "&parse_mode=html"
    )
    response = requests.get(send_text, timeout=10)
    return response.json()


def telegram_bot_send_html_text(token: str, chat_id: str, message_html: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    params = {
        "chat_id": chat_id,
        "text": message_html,  # already HTML-formatted
        "parse_mode": "HTML",
        "link_preview_options": json.dumps({"is_disabled": True}),  # optional
    }
    r = requests.get(url, params=params, timeout=10)
    return r.json()
