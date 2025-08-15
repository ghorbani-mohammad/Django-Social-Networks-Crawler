import html
import json
import re

import requests


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


def collapse_newlines(text: str, max_consecutive: int = 1) -> str:
    """Collapse multiple consecutive blank lines while preserving up to N blank lines.

    A "blank line" is a line that contains only whitespace. Allowing at most
    `max_consecutive` blank lines means we keep at most `max_consecutive + 1`
    newline characters in a row between non-empty lines.

    Args:
        text (str): Input text possibly containing many blank lines.
        max_consecutive (int): Maximum allowed consecutive blank lines. Minimum is 0.

    Returns:
        str: Text with blank lines collapsed and trimmed at both ends.
    """
    if max_consecutive < 0:
        max_consecutive = 0
    # Normalize different line endings to \n first (handles Windows and old Mac)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    # Replace runs of blank lines longer than allowed with exactly the allowed size
    allowed_newlines = "\n" * (max_consecutive + 1)
    collapsed = re.sub(
        r"\n(?:[ \t]*\n){" + str(max_consecutive + 1) + ",}",
        allowed_newlines,
        normalized,
    )
    return collapsed


def strip_accessibility_hashtag_labels(text: str) -> str:
    """Remove LinkedIn a11y 'hashtag' labels while preserving real hashtags.

    - Removes standalone lines that are just 'hashtag' (case-insensitive)
    - Removes the word 'hashtag' when it appears immediately before an actual
      hashtag token (e.g., "hashtag #EdTech" -> "#EdTech")
    """
    # Remove standalone 'hashtag' lines
    text = re.sub(r"(?im)^(?:\s*)hashtag\s*$\n?", "", text)
    # Remove 'hashtag ' before a real hashtag token
    text = re.sub(r"(?i)\bhashtag\s+(?=#[\w\d_])", "", text)
    return text


def normalize_job_message_spacing(text: str) -> str:
    """Ensure desired single-blank-line spacing for LinkedIn job messages.

    Rules:
    - Exactly one blank line AFTER a line starting with "Region:".
    - Exactly one blank line BEFORE a line starting with "Location:".
    - Exactly one blank line AFTER a line starting with "Easy Apply:".
    """
    # Normalize newlines and trim overall
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = normalized.split("\n")
    result = []

    def starts_with(label: str, line: str) -> bool:
        return line.lstrip().lower().startswith(label)

    i = 0
    while i < len(lines):
        line = lines[i]
        result.append(line)

        # After Region:
        if starts_with("region:", line):
            # Skip any existing blank lines following and add exactly one
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines):
                result.append("")
            i = j
            continue

        # After Easy Apply:
        if starts_with("easy apply:", line):
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines):
                result.append("")
            i = j
            continue

        # Before Location:
        if i + 1 < len(lines) and starts_with("location:", lines[i + 1]):
            if result and result[-1] != "":
                result.append("")
        i += 1

    # Join back; general collapse will handle any accidental doubles
    return "\n".join(result).strip()
