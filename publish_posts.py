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
import json
import os

import requests

from footer import footer

API = "https://api.telegram.org/bot{token}/{method}"
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
POSTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "posts_rewrite.json")


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
    parser.add_argument("--mode", choices=["publish", "edit", "both"], default="publish")
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
        if args.mode == "edit":
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
