"""Очередь публикаций.

Задачи живут в publish_queue.json (правите вы), отметка о выполнении —
в кеше Actions (её пишет workflow), поэтому workflow больше ничего не
коммитит в main и не конфликтует с вашими коммитами.

Пример publish_queue.json:
    {
      "pinned": false,
      "delete_ids": [],
      "max_check": false,
      "max_watch": true,
      "max_updates": false,
      "max": null,
      "posts": {"post_id": "all", "mode": "cta", "delete_ids": []}
    }
"""
import hashlib
import json
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE = os.path.join(BASE, "publish_queue.json")


def run(script, *args):
    cmd = [sys.executable, script, *args]
    print("$", " ".join(cmd), flush=True)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("Ошибка:", script, result.returncode)
    return result.returncode == 0


def delete_posts(message_ids):
    import requests

    api = "https://api.telegram.org/bot{token}/{method}"
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHANNEL_ID"]
    ok = True
    for message_id in message_ids:
        r = requests.post(
            api.format(token=token, method="deleteMessage"),
            json={"chat_id": chat_id, "message_id": int(message_id)},
            timeout=60,
        )
        if r.status_code == 200:
            print("Удалён пост:", message_id)
        else:
            print("Не удалось удалить", message_id, "-", r.text[:120])
            ok = False
    return ok


def main():
    with open(QUEUE_FILE, encoding="utf-8") as f:
        raw = f.read()
    queue = json.loads(raw)

    digest = hashlib.sha256(raw.strip().encode()).hexdigest()[:16]
    if "--hash-only" in sys.argv:
        print(digest)
        return
    done = os.environ.get("QUEUE_DONE_HASH", "").strip()
    if done == digest:
        print("Очередь уже выполнялась (хэш", digest, ") — пропускаю.")
        return

    ok = True

    if queue.get("max_watch"):
        print("=== Наблюдение за событиями MAX-бота ===")
        ok = run("max_watch.py") and ok

    if queue.get("max_updates"):
        print("=== События MAX-бота ===")
        ok = run("publish_max.py", "--updates") or ok

    if queue.get("max_ping_chat_id"):
        os.environ["MAX_PING_CHAT_ID"] = str(queue["max_ping_chat_id"])

    if queue.get("max_ping"):
        print("=== Проверка связи с MAX-ботом ===")
        ok = run("publish_max.py", "--ping") and ok

    if queue.get("max_check"):
        print("=== Диагностика MAX-бота ===")
        ok = run("publish_max.py", "--check") and ok

    if queue.get("max"):
        post_id = queue["max"].get("post_id", "all")
        print(f"=== Публикация в MAX: {post_id} ===")
        ok = run("publish_max.py", post_id) and ok

    if queue.get("pinned"):
        print("=== Публикация и закрепление поста-визитки ===")
        ok = run("publish_pinned.py") and ok

    if queue.get("delete_ids"):
        print("=== Удаление постов:", queue["delete_ids"], "===")
        ok = delete_posts(queue["delete_ids"]) and ok

    posts = queue.get("posts")
    if posts:
        post_id = posts.get("post_id", "all")
        delete_ids = posts.get("delete_ids") or []
        mode = posts.get("mode", "publish")
        print(f"=== Посты: {post_id}, режим {mode}, удалить {delete_ids} ===")
        args = [post_id, "--mode", mode]
        if delete_ids:
            args += ["--delete", " ".join(str(i) for i in delete_ids)]
        ok = run("publish_posts.py", *args) and ok

    if not ok:
        print("Очередь выполнена с ошибками — отметка не записана.")
        sys.exit(1)

    print("QUEUE_DONE_HASH:", digest)


if __name__ == "__main__":
    main()
