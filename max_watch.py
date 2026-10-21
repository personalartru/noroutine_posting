"""Следит за событиями MAX-бота и сохраняет их в репозитории.

Событие bot_added содержит chat_id канала, в который бота добавили.
События не теряются: offset хранится в max_offset.txt, журнал — в max_events.log.
"""
import json
import os

from publish_max import TOKEN, call

OFFSET_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "max_offset.txt")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "max_events.log")


def load_offset():
    try:
        with open(OFFSET_FILE, encoding="utf-8") as f:
            return int(f.read().strip() or 0)
    except (OSError, ValueError):
        return 0


def main():
    offset = load_offset()
    try:
        data = call("GET", "updates", query={"offset": offset, "timeout": 0, "limit": 100})
    except RuntimeError as e:
        print("Не удалось получить события:", e)
        return

    events = data.get("updates") or []
    print("Событий:", len(events), "| offset:", offset)

    lines = []
    for event in events:
        kind = event.get("update_type") or event.get("type")
        payload = json.dumps(event, ensure_ascii=False)
        lines.append(f"{kind} {payload}")
        print(" -", kind, "|", payload[:300])

        chat_id = event.get("chat_id")
        if kind == "bot_added" and chat_id:
            try:
                chat = call("GET", f"chats/{chat_id}")
                print("Бот добавлен в чат:", chat.get("title"), "| chat_id:", chat_id)
            except RuntimeError as e:
                print("Чат найден, но недоступен боту:", e)

    if events:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        new_offset = max((e.get("update_id") or 0) for e in events) + 1
        with open(OFFSET_FILE, "w", encoding="utf-8") as f:
            f.write(str(new_offset))
        print("Offset сохранён:", new_offset)
    else:
        print("Новых событий нет.")


if __name__ == "__main__":
    main()
