"""Публикует переписанные посты из posts_rewrite.json в канал.

Примеры:
    python publish_posts.py tracker-triggers
    python publish_posts.py all
    python publish_posts.py tracker-triggers --delete 142 143
    python publish_posts.py all --delete "116 118 119 121 122"

Опции:
    --delete ID [ID ...]  — удалить старые «голые» посты (нужно право
                            «Удаление сообщений» у бота в канале).
"""
import argparse
import html
import json
import os
import re

import requests

from footer import footer

API = "https://api.telegram.org/bot{token}/{method}"
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
POSTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "posts_rewrite.json")
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "noroutine2026")
CTA_MARK = "noroutine_ai_bot"


def api(method, **payload):
    payload = {k: v for k, v in payload.items() if v is not None}
    r = requests.post(API.format(token=TOKEN, method=method), json=payload, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"{method}: HTTP {r.status_code} {r.text[:300]}")
    return r.json().get("result")


def build_text(post):
    parts = [f"<b>{post['title']}</b>", "", post["text"], footer("video")]
    tags = post.get("tags")
    if tags:
        parts += ["", tags]
    return "\n".join(parts)


def publish(post):
    sent = api("sendMessage", chat_id=CHANNEL_ID, text=build_text(post), parse_mode="HTML")
    print("Опубликован:", post["id"], "-> message_id", sent["message_id"])
    return sent["message_id"]


def fetch_current_text(message_id):
    """Текущий текст поста из публичного превью канала."""
    url = f"https://t.me/s/{CHANNEL_USERNAME}?before={int(message_id) + 1}"
    r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    for block in re.split(r'<div class="tgme_widget_message_wrap', r.text)[1:]:
        if f'data-post="{CHANNEL_USERNAME}/{message_id}"' not in block:
            continue
        m = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block, re.S)
        if not m:
            return ""
        text = re.sub(r"<br\s*/?>", "\n", m.group(1))
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()
    return ""


def append_cta(post):
    """Дописать CTA к существующему тексту, ничего не переписывая."""
    message_id = post.get("replace_id")
    if not message_id:
        print("Пропущен (нет старого поста):", post["id"])
        return None
    current = fetch_current_text(message_id)
    if not current:
        print("Не удалось получить текст поста", message_id, "— пропускаю")
        return None
    if CTA_MARK in current:
        print("CTA уже есть, пропускаю:", post["id"])
        return message_id
    cta = footer("video").strip()
    new_text = f"{current}\n\n{cta}"
    api("editMessageText", chat_id=CHANNEL_ID, message_id=message_id,
        text=new_text, parse_mode="HTML", disable_web_page_preview=True)
    print(f"CTA добавлен: {post['id']} (message_id {message_id})")
    print("--- итоговый текст ---")
    print(new_text)
    print("--- конец ---")
    return message_id


def edit(post):
    message_id = post.get("replace_id")
    if not message_id:
        print("Пропущен (нет старого поста для замены):", post["id"])
        return None
    try:
        api("editMessageText", chat_id=CHANNEL_ID, message_id=message_id,
            text=build_text(post), parse_mode="HTML")
        print("Обновлён:", post["id"], "-> message_id", message_id)
        return message_id
    except RuntimeError as e:
        print("Не удалось отредактировать", post["id"], f"({message_id}):", e)
        print("  -> отправьте этот пост заново: --mode publish")
        return None


def delete(message_ids):
    for message_id in message_ids:
        try:
            api("deleteMessage", chat_id=CHANNEL_ID, message_id=message_id)
            print("Удалён старый пост:", message_id)
        except RuntimeError as e:
            print("Не удалось удалить", message_id, "-", e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("post", help="id поста из posts_rewrite.json или all")
    parser.add_argument("--mode", choices=["publish", "edit", "both", "cta"], default="publish")
    parser.add_argument("--delete", nargs="*", type=str, default=[])
    args = parser.parse_args()

    with open(POSTS_FILE, encoding="utf-8") as f:
        posts = json.load(f)

    if args.post == "all":
        selected = posts
    else:
        selected = [p for p in posts if p["id"] == args.post]
        if not selected:
            print("Пост не найден. Доступные id:", ", ".join(p["id"] for p in posts))
            return

    for post in selected:
        if args.mode == "cta":
            append_cta(post)
        elif args.mode == "edit":
            edit(post)
        elif args.mode == "publish":
            publish(post)
        else:
            if post.get("replace_id"):
                edit(post)
            else:
                publish(post)

    ids = []
    for chunk in args.delete:
        ids.extend(int(x) for x in str(chunk).replace(",", " ").split() if x.strip())
    if ids:
        delete(ids)


if __name__ == "__main__":
    main()
