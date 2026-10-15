import json, os, re, sys, datetime
import requests
from urllib.parse import quote

BOT_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID  = os.environ["TELEGRAM_CHANNEL_ID"]
OPENAI_KEY  = os.environ["OPENAI_API_KEY"]
POLLINATIONS_KEY = os.environ.get("POLLINATIONS_API_KEY", "")
TOPICS_FILE = "topics.json"

PROMPT = """Ты — редактор русскоязычного Telegram-канала про автоматизацию рабочих процессов и AI.
Аудитория: IT-команды, digital-агентства, маркетологи, продакты.

Текущий год в мире: 2026. Пиши актуально с позиции 2026 года, опирайся на современные технологии и тренды (никаких устаревших данных из 2023 года).

Тема поста: "{topic}"
{guidance}

Ты — опытный контент-мейкер и эксперт по автоматизации бизнес-процессов в IT (n8n, AI-агенты, скрипты, Яндекс Трекер, облачные функции). 

Твоя задача: написать пост для Telegram-канала "No ! Routine" на заданную тему.

Целевая аудитория: IT-специалисты, менеджеры проектов, HR, маркетологи, предприниматели (уровень: начинающий и средний).
Тон и стиль: неформальный, простой и понятный язык, без "воды" и клише, но с сохранением профессионального IT-контекста. Максимум конкретики и практической пользы.

Структура поста:
1. Описание проблемы или задачи (боль аудитории: рутина, потеря времени, хаос в процессах).
2. Суть решения (практические тезисы, инструменты, шаги).
3. Полезный вывод и обязательный призыв перейти в Дзен за готовыми решениями.

Правила форматирования:
- Используй только HTML-разметку: <b> для заголовков и акцентов, <i> для уточнений, <a href="https://dzen.ru/noroutine">текст ссылки</a> для ссылки на Дзен.
- Маркированные списки оформляй строго через символ • (буллит).
- Не используй Markdown (**, __), только HTML.
- Общий объем текста (блок ===POST===): строго 800–1400 символов с пробелами.
- Теги: 4–6 релевантных хэштегов через пробел в формате #тег.

Строго соблюдай следующую структуру вывода (никаких лишних слов до или после шаблона):

===TITLE===
{Цепляющий заголовок до 80 символов, без HTML-тегов}
===POST===
{Текст поста с HTML-разметкой, списками через • и ссылкой <a href="https://dzen.ru/noroutine">наш Дзен про автоматизацию</a>}
===TAGS===
{4-6 хэштегов через пробел, например: #автоматизация #n8n #менеджмент #AI #IT}

Тема поста для генерации: "{topic}"
===IMAGE===
Короткий промпт НА АНГЛИЙСКОМ для генератора картинок: абстрактная метафора темы,
стиль "clean modern tech illustration, minimal, no text"
"""


def load_topics():
    with open(TOPICS_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_topics(topics):
    with open(TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(topics, f, ensure_ascii=False, indent=2)


def pick_topic(topics):
    today = datetime.date.today().isoformat()
    for i, t in enumerate(topics):
        if t.get("status") == "pending" and t.get("date", today) <= today:
            return i
    return None


def generate(topic, guidance):
    guidance_block = f"Дополнительные требования: {guidance}" if guidance else ""
    
    # Экранируем фигурные скобки внутри PROMPT перед .format(), кроме {topic} и {guidance}
    safe_prompt_template = PROMPT.replace("{", "{{").replace("}", "}}")
    safe_prompt_template = safe_prompt_template.replace("{{topic}}", "{topic}").replace("{{guidance}}", "{guidance}")
    
    formatted_prompt = safe_prompt_template.format(topic=topic, guidance=guidance_block)

    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_KEY}"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": formatted_prompt}],
            "temperature": 0.7
        },
        timeout=180,
    )
    r.raise_for_status()
    
    data = r.json()
    text = data["choices"][0]["message"]["content"]

    def grab(name):
        m = re.search(rf"==={name}===\s*(.*?)(?====|\Z)", text, re.S)
        return m.group(1).strip() if m else ""

    return {
        "title": grab("TITLE"),
        "post":  grab("POST"),
        "tags":  grab("TAGS"),
        "image": grab("IMAGE") or "abstract tech automation, clean minimal illustration",
    }


def send_photo(prompt):
    url = (f"https://image.pollinations.ai/prompt/{quote(prompt)}"
           f"?width=1280&height=720&nologo=true&model=flux")
    headers = {}
    if POLLINATIONS_KEY:
        headers["Authorization"] = f"Bearer {POLLINATIONS_KEY}"
        
    img = requests.get(url, headers=headers, timeout=180)
    img.raise_for_status()
    return requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
        data={"chat_id": CHANNEL_ID},
        files={"photo": ("cover.jpg", img.content)},
        timeout=120,
    ).json()


def send_message(text):
    return requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHANNEL_ID, "text": text,
              "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=60,
    ).json()


def main():
    topics = load_topics()
    idx = pick_topic(topics)
    if idx is None:
        print("Нет тем к публикации на сегодня."); return

    item = topics[idx]
    s = generate(item["topic"], item.get("guidance", ""))
    full_text = f"<b>{s['title']}</b>\n\n{s['post']}\n\n{s['tags']}"

    try:
        res_photo = send_photo(s["image"])
        if not res_photo.get("ok"):
            print("Предупреждение: не удалось отправить фото, шлем только текст:", res_photo)
    except Exception as e:
        print(f"Предупреждение: ошибка генерации/отправки фото ({e}), шлем только текст.")

    res = send_message(full_text)

    if res.get("ok"):
        item["status"] = "published"
        item["published_at"] = datetime.datetime.utcnow().isoformat()
        save_topics(topics)
        print("Опубликовано:", s["title"])
    else:
        print("Ошибка публикации текста:", res)
        sys.exit(1)


if __name__ == "__main__":
    main()
