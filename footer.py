"""Футер постов: ссылка на бот с лид-магнитом.

Текст добавляется в конец каждого поста автоматического публикатора и в
переписанные посты. Если секрет BOT_USERNAME не задан, футер не добавляется.
"""
import os

BOT_USERNAME = os.environ.get("BOT_USERNAME", "").lstrip("@")

FOOTER = (
    "\n\n👉 5 готовых n8n-воркфлоу (Трекер, Формы, Google Таблицы, боты в Telegram и MAX) "
    "— импорт в n8n за минуту, бесплатно: https://t.me/{bot}?start=auto"
)

FOOTER_SOURCE = (
    "\n\n👉 5 готовых n8n-воркфлоу (Трекер, Формы, Google Таблицы, боты в Telegram и MAX) "
    "— импорт в n8n за минуту, бесплатно: https://t.me/{bot}?start=video"
)


def footer(source="auto"):
    if not BOT_USERNAME:
        return ""
    template = FOOTER_SOURCE if source == "video" else FOOTER
    return template.format(bot=BOT_USERNAME)
