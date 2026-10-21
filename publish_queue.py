"""Выполняет очередь публикаций из publish_queue.json.

Очередь — обычный файл в репозитории, поэтому публикацию можно запустить
просто коммитом: вписать задачу в publish_queue.json и запушить.

Пример файла очереди:
    {
      "pinned": true,
      "delete_ids": [],
      "max": {"post_id": "all"},
      "posts": {"post_id": "all", "mode": "cta"}
    }

- "pinned": true — опубликовать и закрепить пост-визитку.
- "posts.post_id": "all" или id из posts_rewrite.json.
- "posts.delete_ids": старые посты, которые нужно удалить (только если
  post_id публикует новые посты, а не редактирует существующие).
"""
import json
import os
import subprocess
import sys

QUEUE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "publish_queue.json")


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


def run(script, *args):
    cmd = [sys.executable, script, *args]
    print("$", " ".join(cmd), flush=True)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("Ошибка:", script, result.returncode)
    return result.returncode == 0


def main():
    with open(QUEUE_FILE, encoding="utf-8") as f:
        queue = json.load(f)

    done = False

    if queue.get("pinned"):
        print("=== Публикация и закрепление поста-визитки ===")
        done = run("publish_pinned.py") or done

    delete_ids = queue.get("delete_ids") or []
    if delete_ids:
        print("=== Удаление постов:", delete_ids, "===")
        done = delete_posts(delete_ids) or done

    if queue.get("max_updates"):
        print("=== События MAX-бота ===")
        done = run("publish_max.py", "--updates") or done

    if queue.get("max_check"):
        print("=== Диагностика MAX-бота ===")
        done = run("publish_max.py", "--check") or done

    max_task = queue.get("max")
    if max_task:
        post_id = max_task.get("post_id", "all")
        print(f"=== Публикация в MAX: {post_id} ===")
        done = run("publish_max.py", post_id) or done

    posts = queue.get("posts")
    if posts:
        post_id = posts.get("post_id", "all")
        delete_ids = posts.get("delete_ids") or []
        mode = posts.get("mode", "publish")
        print(f"=== Посты: {post_id}, режим {mode}, удалить {delete_ids} ===")
        args = [post_id, "--mode", mode]
        if delete_ids:
            args += ["--delete", " ".join(str(i) for i in delete_ids)]
        done = run("publish_posts.py", *args) or done

    if not done:
        print("Очередь пуста или шаги не выполнены — проверьте publish_queue.json")
    else:
        print("Очередь выполнена.")


if __name__ == "__main__":
    main()
