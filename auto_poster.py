import json, os, re, sys, datetime
import requests
from urllib.parse import quote

BOT_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID  = os.environ["TELEGRAM_CHANNEL_ID"]
OPENAI_KEY  = os.environ["OPENAI_API_KEY"]
POLLINATIONS_KEY = os.environ.get("POLLINATIONS_API_KEY", "") # Опциональный ключ
TOPICS_FILE = "topics.json"

PROMPT = """Ты — редактор русскоязычного Telegram-канала про автоматизацию рабочих процессов и AI.
Аудитория: IT-команды, digital-агентства, маркетологи, продакты.

Тема поста: "{topic}"
{guidance}

Используя свои знания, напиши экспертный, актуальный пост для Telegram НА РУССКОМ ЯЗЫКЕ.
Верни ответ СТРОГО в этом формате, без лишнего текста и без оберток вроде ```markdown:
===TITLE===
Цепляющий заголовок до 80 символов (на русском)
===POST===
Текст 800–1400 символов на русском. HTML-разметка (<b>, <i>, <a href="">),
списки через •, конкретика и практические тезисы, без воды.
===TAGS===
4–6 РЕЛЕВАНТНЫХ теме хэштегов через пробел в формате #тег
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
    
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_KEY}"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": PROMPT.format(topic=topic, guidance=guidance_block)}],
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

    # Пытаемся отправить картинку, если падает — отправляем только текст
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
