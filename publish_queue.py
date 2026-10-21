"""Выполняет очередь публикаций из publish_queue.json.

Очередь — обычный файл в репозитории, поэтому публикацию можно запустить
просто коммитом: вписать задачу в publish_queue.json и запушить.

Пример файла очереди:
    {
      "pinned": true,
      "posts": {"post_id": "all", "delete_ids": [116, 118, 119, 121, 122]}
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
