"""Публикует посты запуска в MAX-канале и закрепляет первый.

Нужны секреты MAX_BOT_TOKEN (бот-админ канала) и MAX_CHANNEL_ID
(числовой ID канала, например 71062363105923).

Пример:
    python publish_max.py all
    python publish_max.py max-visi
"""
import json
import os
import sys

import requests

from max_poster import upload_image

API = "https://platform-api2.max.ru"
TOKEN = os.environ["MAX_BOT_TOKEN"]
CHANNEL_ID = os.environ["MAX_CHANNEL_ID"]
POSTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "max_launch_posts.json")
CARD_PATH = "max_card.jpg"


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
        raise RuntimeError(f"{method} {path}: HTTP {r.status_code} {r.text[:300]}")
    return r.json()


def resolve_chat_id():
    """У MAX chat_id канала отрицательный: -71062363105923, а не 71062363105923."""
    global CHANNEL_ID
    candidates = [CHANNEL_ID]
    if not CHANNEL_ID.startswith("-"):
        candidates.append(f"-{CHANNEL_ID}")
    for candidate in candidates:
        try:
            call("GET", f"chats/{candidate}")
            if candidate != CHANNEL_ID:
                print("chat_id уточнён:", candidate)
            CHANNEL_ID = candidate
            return CHANNEL_ID
        except RuntimeError:
            continue
    return CHANNEL_ID


def check():
    """Диагностика: бот живой, видит ли канал, что закреплено."""
    resolve_chat_id()
    me = call("GET", "me")
    print("Бот:", me.get("username"), "|", me.get("name") or me.get("first_name"))
    try:
        chat = call("GET", f"chats/{CHANNEL_ID}")
        print("Канал:", chat.get("title"), "| подписчиков:", chat.get("members_count") or chat.get("subscriber_count"))
        print("Описание:", (chat.get("description") or "")[:200].replace("\n", " | "))
    except RuntimeError as e:
        print("Канал недоступен боту:", e)
        print("  -> добавьте бота администратором канала и проверьте MAX_CHANNEL_ID")
    try:
        messages = call("GET", "messages", query={"chat_id": CHANNEL_ID, "limit": 10})
        items = messages.get("messages") or []
        print("Постов в канале (по API):", len(items))
        for item in items[:6]:
            body = (item.get("body") or {})
            text = (body.get("text") or "").replace("\n", " ")
            print("  -", text[:90])
    except RuntimeError as e:
        print("Список постов не прочитан:", e)
    try:
        pinned = call("GET", f"chats/{CHANNEL_ID}/pin")
        message = pinned.get("message") or pinned
        body = (message or {}).get("body") or {}
        print("Закреплённый пост:", body.get("mid"), "->", (body.get("text") or "")[:80])
    except RuntimeError as e:
        print("Закреп не читается:", e)


def updates():
    """События бота: bot_added содержит реальный chat_id канала."""
    try:
        data = call("GET", "updates", query={"timeout": 0, "limit": 100})
    except RuntimeError as e:
        print("Не удалось получить события:", e)
        return
    events = data.get("updates") or []
    print("Событий:", len(events))
    seen_chats = {}
    for event in events:
        kind = event.get("update_type") or event.get("type")
        chat_id = event.get("chat_id")
        if chat_id:
            seen_chats[chat_id] = kind
        print(" -", kind, "| chat_id:", chat_id, "|", json.dumps(event, ensure_ascii=False)[:220])
    if seen_chats:
        print("\nВозможные chat_id:", seen_chats)


def make_card(title):
    from PIL import Image, ImageDraw, ImageFont

    width, height = 1280, 720
    img = Image.new("RGB", (width, height), color=(11, 15, 25))
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 40, width - 40, height - 40], outline=(0, 200, 255), width=2)
    draw.rectangle([52, 52, width - 52, height - 52], outline=(100, 50, 255), width=1)

    font_large = font_small = None
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                 "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                 "/Library/Fonts/Arial Bold.ttf"):
        if os.path.exists(path):
            try:
                font_large = ImageFont.truetype(path, 54)
                font_small = ImageFont.truetype(path, 28)
                break
            except OSError:
                pass
    if not font_large:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw.text((80, 90), "🤖 AI & AUTOMATION", fill=(0, 200, 255), font=font_small)
    draw.text((80, height - 90), "NoRoutine • MAX • Автоматизация & AI",
              fill=(140, 150, 180), font=font_small)

    words = title.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        try:
            width_px = font_large.getlength(test)
        except AttributeError:
            width_px = font_large.getbbox(test)[2]
        if width_px <= 1100:
            current = test
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    y = (height - len(lines) * 70) // 2 + 20
    for line in lines:
        draw.text((80, y), line, fill=(255, 255, 255), font=font_large)
        y += 70

    img.save(CARD_PATH, quality=95)
    return CARD_PATH


def publish(post):
    body = {"text": post["text"], "format": "html", "notify": True}
    if post.get("image"):
        media_token = upload_image(TOKEN, make_card("No ! Routine"))
        body["attachments"] = [{"type": "image", "payload": {"token": media_token}}]

    data = call("POST", "messages", query={"chat_id": CHANNEL_ID}, body=body)
    message = data.get("message", {})
    message_id = (message.get("body") or {}).get("mid") or message.get("message_id")
    print(f"Опубликован в MAX: {post['id']} -> mid {message_id}")
    return message_id


def pin(message_id):
    try:
        call("PUT", f"chats/{CHANNEL_ID}/pin", body={"message_id": str(message_id), "notify": False})
        print("Пост закреплён в MAX:", message_id)
    except RuntimeError as e:
        print("Не удалось закрепить (нужно право «Закрепление сообщений»):", e)


def main():
    resolve_chat_id()
    if "--check" in sys.argv:
        check()
        return
    if "--updates" in sys.argv:
        updates()
        return

    with open(POSTS_FILE, encoding="utf-8") as f:
        posts = json.load(f)

    if len(sys.argv) < 2 or sys.argv[1] == "all":
        selected = posts
    else:
        selected = [p for p in posts if p["id"] == sys.argv[1]]
        if not selected:
            print("Пост не найден. Доступные id:", ", ".join(p["id"] for p in posts))
            return

    for post in selected:
        message_id = publish(post)
        if post.get("pin") and message_id:
            pin(message_id)


if __name__ == "__main__":
    main()
