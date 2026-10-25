"""Исправляет ссылки в уже опубликованных постах MAX-канала.

Заменяет ссылку на Telegram-бота (https://t.me/noroutine_ai_bot?...)
на MAX-диплинк (https://max.ru/{MAX_BOT_USERNAME}?...).

Запуск (секреты MAX_BOT_TOKEN, MAX_CHANNEL_ID, MAX_BOT_USERNAME):
    python fix_max_links.py             # dry-run: только показать
    python fix_max_links.py --apply     # внести правки
"""
import os
import sys

import requests

API = "https://platform-api2.max.ru"
TOKEN = os.environ["MAX_BOT_TOKEN"]
CHANNEL_ID = os.environ.get("MAX_CHANNEL_ID", "-71062363105923")
MAX_BOT = os.environ.get("MAX_BOT_USERNAME", "se14730534_bot").lstrip("@")
APPLY = "--apply" in sys.argv

TG_LINK = "https://t.me/noroutine_ai_bot"
MAX_LINK = f"https://max.ru/{MAX_BOT}"

COUNT = os.environ.get("MAX_FIX_COUNT", "100")


def call(method, path, query=None, body=None):
    r = requests.request(
        method,
        f"{API}/{path}",
        params=query,
        headers={"Authorization": TOKEN, "Content-Type": "application/json"},
        json=body,
        timeout=90,
    )
    if r.status_code != 200:
        raise RuntimeError(f"{method} {path}: HTTP {r.status_code} {r.text[:200]}")
    return r.json()


def resolve_chat_id():
    global CHANNEL_ID
    candidates = [CHANNEL_ID]
    if not str(CHANNEL_ID).startswith("-"):
        candidates.append(f"-{CHANNEL_ID}")
    for candidate in candidates:
        try:
            call("GET", f"chats/{candidate}")
            CHANNEL_ID = candidate
            return candidate
        except RuntimeError:
            continue
    return CHANNEL_ID


def edit_message(message_id, text):
    """Пробует несколько вариантов эндпоинта редактирования сообщения."""
    body = {"text": text, "format": "html"}
    variants = [
        ("PUT", f"messages?message_id={message_id}", {"message_id": str(message_id)}),
        ("PUT", f"messages/{message_id}", None),
        ("POST", f"messages/edit/{message_id}", None),
    ]
    last_err = None
    for method, path, query in variants:
        try:
            r = requests.request(
                method,
                f"{API}/{path}",
                params=query,
                headers={"Authorization": TOKEN, "Content-Type": "application/json"},
                json=body,
                timeout=90,
            )
            if r.status_code == 200:
                return True
            last_err = f"HTTP {r.status_code}: {r.text[:120]}"
        except Exception as e:
            last_err = str(e)
    print(f"    не удалось отредактировать mid {message_id}: {last_err}")
    return False


def main():
    resolve_chat_id()
    data = call("GET", "messages", query={"chat_id": CHANNEL_ID, "count": int(COUNT)})
    items = data.get("messages") or []
    print(f"Постов в канале: {len(items)}")
    found = 0
    fixed = 0
    for item in items:
        body = item.get("body") or {}
        mid = body.get("mid") or item.get("message_id")
        text = body.get("text") or ""
        if TG_LINK in text:
            found += 1
            new_text = text.replace(TG_LINK, MAX_LINK)
            print(f"mid {mid}: найдена ссылка на Telegram-бота")
            if APPLY:
                if edit_message(mid, new_text):
                    print(f"  -> заменена на {MAX_LINK}")
                    fixed += 1
            else:
                print(f"  (dry-run, замена -> {MAX_LINK})")
    print(f"\nИтого: {found} постов со ссылкой на Telegram, {fixed} исправлено.")


if __name__ == "__main__":
    main()
