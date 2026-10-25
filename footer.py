"""Футер постов: ссылка на бота с лид-магнитом — своя для Telegram и для MAX.

Текст добавляется в конец каждого поста автоматического публикатора.
Если username для платформы не задан, футер для неё не добавляется
(для MAX используется резервная ссылка на канал).
"""
import os

TG_BOT = os.environ.get("BOT_USERNAME", "").lstrip("@")
MAX_BOT = os.environ.get("MAX_BOT_USERNAME", "").lstrip("@")
MAX_CHANNEL = os.environ.get("MAX_CHANNEL_USERNAME", "channel_noroutine").lstrip("@")

TEXT = (
    "\n\n👇 Приветственный бонус: 5 готовых n8n-воркфлоу (импорт в n8n за минуту) "
    "— бесплатно после подписки:\n"
)

TG_LINK = "https://t.me/{bot}?start={src}"
MAX_LINK = "https://max.ru/{bot}?start={src}"
MAX_FALLBACK = "https://max.ru/{chan}"


def footer(source="auto", platform="tg"):
    src = "video" if source == "video" else "auto"
    if platform == "max":
        if MAX_BOT:
            return TEXT + MAX_LINK.format(bot=MAX_BOT, src=src)
        if MAX_CHANNEL:
            return TEXT + MAX_FALLBACK.format(chan=MAX_CHANNEL)
        return ""
    if not TG_BOT:
        return ""
    return TEXT + TG_LINK.format(bot=TG_BOT, src=src)
