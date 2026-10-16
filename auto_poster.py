import json, os, re, sys, datetime
import requests
from urllib.parse import quote

BOT_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID  = os.environ["TELEGRAM_CHANNEL_ID"]
OPENAI_KEY  = os.environ["OPENAI_API_KEY"]
TOPICS_FILE = "topics.json"

PROMPT = """Ты — редактор русскоязычного Telegram-канала про автоматизацию рабочих процессов и AI.
Аудитория: IT-команды, digital-агентства, маркетологи, продакты.

Текущий год в мире: 2026. Пиши актуально с позиции 2026 года, опирайся на современные технологии и тренды.

Тема поста: "{topic}"
{guidance}

Используя свои знания, напиши увлекательный, экспертный пост для Telegram НА РУССКОМ ЯЗЫКЕ в следующем стиле и структуре:
- Заголовок с ярким эмодзи в начале (например: 🚀 [Заголовок])
- Краткая проблема (почему это важно/болит)
- Суть трендов / тезисов в виде красивых пунктов с эмодзи (название, суть, польза)
- Мотивирующий вывод / призыв к действию в конце
- Хэштеги в самом низу

Верни ответ СТРОГО в этом формате, без лишнего текста и без оберток вроде ```markdown:
===TITLE===
🚀 Заголовок с эмодзи
===POST===
Текст поста с HTML-разметкой (<b>, <i>, <a href="">) и структурой.
===TAGS===
#тег1 #тег2 #тег3 #тег4
===IMAGE===
Подробный промпт НА АНГЛИЙСКОМ для DALL-E 3: современная минималистичная технологическая иллюстрация для IT-поста, яркие цвета, без текста, векторный или 3D стиль.
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
        "image": grab("IMAGE") or "Clean modern tech illustration, minimal, no text",
    }


def send_photo(prompt):
    # Генерация картинки через OpenAI DALL-E 3
    r = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {OPENAI_KEY}"},
        json={
            "model": "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024"
        },
        timeout=120,
    )
    r.raise_for_status()
    image_url = r.json()["data"][0]["url"]

    # Скачиваем полученную картинку
    img = requests.get(image_url, timeout=120)
    img.raise_for_status()

    return requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
        data={"chat_id": CHANNEL_ID},
        files={"photo": ("cover.png", img.content)},
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
        print(f"Предупреждение: ошибка генерации/отправки фото через DALL-E ({e}), шлем только текст.")

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
