"""Публикует закреплённый пост канала и закрепляет его.

Запуск: python publish_pinned.py
Нужны секреты TELEGRAM_BOT_TOKEN и TELEGRAM_CHANNEL_ID, плюс BOT_USERNAME —
юзернейм бота, который выдаёт лид-магнит (для ссылки в посте).
"""
import os
import sys

import requests

API = "https://api.telegram.org/bot{token}/{method}"
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
BOT_USERNAME = os.environ.get("BOT_USERNAME", "").lstrip("@")
POST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pinned_post.txt")
PLACEHOLDER = "BOT_USERNAME_PLACEHOLDER"


def api(method, **payload):
    payload = {k: v for k, v in payload.items() if v is not None}
    r = requests.post(API.format(token=TOKEN, method=method), json=payload, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"{method}: HTTP {r.status_code} {r.text[:300]}")
    return r.json().get("result")


def main():
    with open(POST_FILE, encoding="utf-8") as f:
        text = f.read().strip()

    if PLACEHOLDER in text:
        if not BOT_USERNAME:
            print("Не задан BOT_USERNAME — ссылка на бота останется плейсхолдером.")
            sys.exit(1)
        text = text.replace(PLACEHOLDER, BOT_USERNAME)

    buttons = None
    if BOT_USERNAME:
        buttons = {
            "inline_keyboard": [[{
                "text": "Получить 5 воркфлоу",
                "url": f"https://t.me/{BOT_USERNAME}?start=pinned",
            }]]
        }

    sent = api(
        "sendMessage",
        chat_id=CHANNEL_ID,
        text=text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=buttons,
    )
    message_id = sent["message_id"]
    print("Пост отправлен:", message_id)

    try:
        api("pinChatMessage", chat_id=CHANNEL_ID, message_id=message_id, disable_notification=True)
        print("Пост закреплён.")
    except RuntimeError as e:
        print("Не удалось закрепить (нужно право «Закрепление сообщений»):", e)


if __name__ == "__main__":
    main()
