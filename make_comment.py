"""Готовит экспертный ответ для комментария в Telegram-чате.

Вы кладёте вопрос в assist_queue.json и пушите — workflow генерирует
2-3 варианта ответа в вашем стиле и дописывает их в assist_answers.md
и в трекер комментинга.

Запуск: python make_comment.py
"""
import json
import os
import re
from datetime import datetime, timezone

import requests

OPENAI_KEY = os.environ["OPENAI_API_KEY"]
QUEUE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assist_queue.json")
ANSWERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assist_answers.md")
TRACKER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "commenting_tracker.md")
MODEL = "gpt-4o-mini"

PROMPT = """Ты — Павел Новиков, эксперт по автоматизации бизнес-процессов в digital
и проектном управлении. 15+ лет в IT и PM, ставил n8n, AI-агентов, скрипты,
облачные функции, связки с Яндекс Трекером, Google Sheets, Telegram и MAX.
Стиль: деловой, без воды, по делу, с конкретикой и числами. Без канцелярита,
без «в современном мире», без хайпа.

Вопрос в чате:
{question}

Чат: {chat}
{notes}

Напиши {variants} варианта ответа на русском (если вопрос на английском —
отвечай на английском). Требования:
- 3-6 предложений, по делу, как практик, а не как маркетолог;
- без рекламы и без ссылки на канал в первом варианте;
- второй и третий варианты — короче и разговорчивее, можно с мягкой ссылкой
  на Telegram-канал (t.me/noroutine2026), только если это уместно по сути
  вопроса; ссылку давай в конце, отдельной строкой, только в 3-м варианте;
- если вопрос по теме вне автоматизации — отвечай коротко и по делу, без
  навязчивых предложений;
- не выдумывай факты, которых нет в вопросе; непонятное — уточни.

Верни ТОЛЬКО варианты, каждый с новой строки, в формате:
### Вариант N
<текст ответа>
"""


def generate(question, chat, notes, variants=3):
    prompt = PROMPT.format(question=question, chat=chat or "не указан", notes=notes or "", variants=variants)
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_KEY}"},
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.8,
        },
        timeout=180,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def append_answers(question, chat, text):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    block = f"\n## {stamp} · чат: {chat or '—'}\n\n**Вопрос:** {question}\n\n{text}\n"
    with open(ANSWERS_FILE, "a", encoding="utf-8") as f:
        f.write(block)


def append_tracker(chat, question):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = f"| {stamp} | {chat or '—'} | {question[:60]} | ⬜ отправлен | ⬜ | ⬜ |\n"
    path = TRACKER_FILE
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write("# Трекер комментинга\n\n"
                    "| дата | чат | вопрос | отправлен | ответ | прирост |\n"
                    "|---|---|---|---|---|---|\n")
    with open(path, "a", encoding="utf-8") as f:
        f.write(row)


def main():
    with open(QUEUE_FILE, encoding="utf-8") as f:
        queue = json.load(f)

    question = (queue.get("question") or "").strip()
    if not question:
        print("В assist_queue.json нет вопроса — заполните поле question.")
        return

    chat = queue.get("chat") or ""
    notes = queue.get("notes") or ""
    variants = int(queue.get("variants") or 3)

    print("Генерирую варианты ответа…")
    text = generate(question, chat, notes, variants)

    print("\n" + text)
    append_answers(question, chat, text)
    append_tracker(chat, question)
    print("\nСохранено в assist_answers.md и commenting_tracker.md")


if __name__ == "__main__":
    main()
