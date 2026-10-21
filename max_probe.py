"""Перебор вариантов chat_id канала: в MAX id канала отрицательный."""
import base64
import os

from publish_max import call

BASE_ID = os.environ.get("MAX_CHANNEL_ID", "71062363105923")

CANDIDATES = [
    BASE_ID,
    f"-{BASE_ID}",
    f"-100{BASE_ID}",
    f"100{BASE_ID}",
    f"-{BASE_ID}0",
    f"-100{BASE_ID}0",
]


def safe(value):
    return base64.b64encode(str(value).encode()).decode()


def main():
    for candidate in CANDIDATES:
        try:
            chat = call("GET", f"chats/{candidate}")
            print("ПОДХОДИТ:", safe(candidate), "| type:", chat.get("type"),
                  "| title:", chat.get("title"))
        except RuntimeError as e:
            print("нет:", safe(candidate), "|", str(e)[:90])


if __name__ == "__main__":
    main()
