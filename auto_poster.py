import json, os, re, sys, datetime
import requests
from PIL import Image, ImageDraw, ImageFont

BOT_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID  = os.environ["TELEGRAM_CHANNEL_ID"]
OPENAI_KEY  = os.environ["OPENAI_API_KEY"]
TOPICS_FILE = "topics.json"

PROMPT = """Ты — редактор русскоязычного Telegram-канала про автоматизацию рабочих процессов и AI.
Аудитория: IT-команды, digital-агентства, маркетологи, продакты.

Текущий год в мире: 2026. Пиши актуально с позиции 2026 года, опирайся на современные технологии и тренды.

Тема поста: "{topic}"
Дополнительные указания / контекст: {guidance}
{link_instruction}

Напиши пост НА РУССКОМ ЯЗЫКЕ строго по этому сценарию: неформально, живо, без клише, штампов и канцелярита. Пиши так, как пишет человек, а не пресс-релиз. Строго повтори структуру примера:

ЗАГОЛОВОК (одна строка): [эмодзи] [цепкий заголовок с числом и месяцем/годом, например: 🚀 5 трендов автоматизации в IT (октябрь 2026)]

Проблема: 1-2 предложения о реальной боли (например: рутина съедает до 30% времени. Вместо фич мы сводим отчёты и отвечаем на одни и те же вопросы).

Задача: одна строка — что хотим получить (например: вернуть время команде на созидание).

Суть (заголовок вида «Суть трендов:» / «Суть пунктов:»), затем список из 3-6 пунктов, КАЖДЫЙ пункт отдельной строкой строго в формате:
[эмодзи] [Название]: [суть в 1 предложении]. Польза: [конкретная измеримая польза].
Пример: 🤖 AI-агенты: сами создают задачи в трекере при инцидентах. Польза: реакция за секунды, а не за часы.

Вывод: 1-2 предложения с призывом к действию. Если дана ссылка — обязательно вплети её в вывод (см. инструкцию про ссылку выше).

Никаких вступлений вроде «Конечно, вот пост». Не используй фразы-клише («в современном мире», «не секрет, что», «играет важную роль»). Эмодзи — только в начале заголовка и в начале пунктов списка.

Верни ответ СТРОГО в этом формате, без лишнего текста и без оберток вроде ```markdown:
===TITLE===
🚀 Заголовок с эмодзи
===POST===
Заголовок (можно <b>...</b>), затем пустая строка, «Проблема: ...», пустая строка, «Задача: ...», пустая строка, «Суть ...:», список пунктов, пустая строка, вывод. Разрешена HTML-разметка: <b>, <i>, <a href="">.
===TAGS===
#тег1 #тег2 #тег3 #тег4
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


def generate(topic, guidance, link_text, link_url):
    guidance_block = f"{guidance}" if guidance else ""
    text_link = link_text or "Подробнее"
    link_inst = f"Обязательно добавь в конец текста (перед хэштегами) кликабельную ссылку с текстом '{text_link}' на этот URL: {link_url} в формате HTML (<a href='{link_url}'>{text_link}</a>)." if link_url else ""
    
    safe_prompt_template = PROMPT.replace("{", "{{").replace("}", "}}")
    safe_prompt_template = safe_prompt_template.replace("{{topic}}", "{topic}").replace("{{guidance}}", "{guidance}").replace("{{link_instruction}}", "{link_instruction}")
    
    formatted_prompt = safe_prompt_template.format(topic=topic, guidance=guidance_block, link_instruction=link_inst)

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

    post_content = grab("POST")

    # Приводим markdown-ссылки модели к HTML, понятному Telegram
    post_content = re.sub(r'\[([^\]]+)\]\((https?://[^\s)]+)\)', r'<a href="\2">\1</a>', post_content)

    # Ссылку из админки добавляем в конец, если её ещё нет как HTML-анкера.
    # Достаточно URL; текст ссылки необязателен.
    if link_url and not re.search(rf'<a\s+href="{re.escape(link_url)}"', post_content):
        text_link = link_text or "Подробнее"
        post_content += f'\n\n🔗 <a href="{link_url}">{text_link}</a>'

    return {
        "title": grab("TITLE"),
        "post":  post_content,
        "tags":  grab("TAGS"),
    }


def create_branded_card(title_text):
    width, height = 1280, 720
    img = Image.new("RGB", (width, height), color=(11, 15, 25))
    draw = ImageDraw.Draw(img)

    draw.rectangle([40, 40, width - 40, height - 40], outline=(0, 200, 255), width=2)
    draw.rectangle([52, 52, width - 52, height - 52], outline=(100, 50, 255), width=1)

    font_large = None
    font_small = None
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf"
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                font_large = ImageFont.truetype(path, 54)
                font_small = ImageFont.truetype(path, 28)
                break
            except:
                pass
                
    if not font_large:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw.text((80, 90), "🤖 AI & AUTOMATION", fill=(0, 200, 255), font=font_small)

    def wrap_text(text, font, max_width):
        lines = []
        words = text.split()
        current_line = ""
        for word in words:
            test_line = current_line + " " + word if current_line else word
            try:
                w = font.getlength(test_line)
            except:
                w = font.getbbox(test_line)[2]
            if w <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        return lines

    wrapped_lines = wrap_text(title_text, font_large, max_width=1100)
    line_height = 70
    total_text_height = len(wrapped_lines) * line_height
    start_y = (height - total_text_height) // 2 + 20

    current_y = start_y
    for line in wrapped_lines:
        draw.text((80, current_y), line, fill=(255, 255, 255), font=font_large)
        current_y += line_height

    draw.text((80, height - 90), "NoRoutine • Автоматизация & AI", fill=(140, 150, 180), font=font_small)

    card_path = "branded_card.jpg"
    img.save(card_path, quality=95)
    return card_path


def send_photo(photo_source):
    # Проверяем, это URL или локальный файл
    if photo_source.startswith("http://") or photo_source.startswith("https://"):
        img_data = requests.get(photo_source, timeout=60).content
        return requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={"chat_id": CHANNEL_ID},
            files={"photo": ("cover.jpg", img_data)},
            timeout=120,
        ).json()
    else:
        with open(photo_source, "rb") as photo:
            return requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                data={"chat_id": CHANNEL_ID},
                files={"photo": ("cover.jpg", photo)},
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
    s = generate(item["topic"], item.get("guidance", ""), item.get("linkText", ""), item.get("linkUrl", ""))
    
    tags = item.get("tags") or s['tags']
    full_text = f"<b>{s['title']}</b>\n\n{s['post']}\n\n{tags}"

    try:
        # Если в админке указана своя картинка — берем её, иначе генерируем карточку
        custom_image = item.get("imageUrl")
        if custom_image:
            res_photo = send_photo(custom_image)
        else:
            card_path = create_branded_card(s['title'])
            res_photo = send_photo(card_path)

        if not res_photo.get("ok"):
            print("Предупреждение: не удалось отправить фото, шлем только текст:", res_photo)
    except Exception as e:
        print(f"Предупреждение: ошибка отправки фото ({e}), шлем только текст.")

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
