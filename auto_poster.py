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
    }


def create_branded_card(title_text):
    # Создаем холст 1280x720 (16:9) с темно-синим IT-фоном
    width, height = 1280, 720
    img = Image.new("RGB", (width, height), color=(11, 15, 25) # Темный премиальный фон
    )
    draw = ImageDraw.Draw(img)

    # Рисуем неоновые фоновые элементы / градиентные полосы
    draw.rectangle([40, 40, width - 40, height - 40], outline=(0, 200, 255), width=2) # Неоновая рамка
    draw.rectangle([52, 52, width - 52, height - 52], outline=(100, 50, 255), width=1) # Вторая линия

    # Попытка загрузить системный шрифт (или стандартный дефолтный)
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

    # Рисуем плашку категории сверху
    category_text = "🤖 AI & AUTOMATION"
    draw.text((80, 90), category_text, fill=(0, 200, 255), font=font_small)

    # Функция для переноса строк текста по ширине
    def wrap_text(text, font, max_width):
        lines = []
        words = text.split()
        current_line = ""
        for word in words:
            test_line = current_line + " " + word if current_line else word
            # В Pillow 10+ используем getlength, в старых bbox
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

    # Формируем заголовок (убираем лишние эмодзи из технической части если нужно, но оставим как есть)
    clean_title = re.sub(r'^[^\w\s]+\s*', '', title_text) # Опционально чистим первый символ если мешает
    wrapped_lines = wrap_text(title_text, font_large, max_width=1100)

    # Вычисляем общую высоту текста для центрирования по вертикали
    line_height = 70
    total_text_height = len(wrapped_lines) * line_height
    start_y = (height - total_text_height) // 2 + 20

    # Отрисовка строк заглавия
    current_y = start_y
    for line in wrapped_lines:
        draw.text((80, current_y), line, fill=(255, 255, 255), font=font_large)
        current_y += line_height

    # Нижний колонтитул
    draw.text((80, height - 90), "NoRoutine • Автоматизация & AI", fill=(140, 150, 180), font=font_small)

    card_path = "branded_card.jpg"
    img.save(card_path, quality=95)
    return card_path


def send_photo(card_path):
    with open(card_path, "rb") as photo:
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
    s = generate(item["topic"], item.get("guidance", ""))
    full_text = f"<b>{s['title']}</b>\n\n{s['post']}\n\n{s['tags']}"

    try:
        card_path = create_branded_card(s['title'])
        res_photo = send_photo(card_path)
        if not res_photo.get("ok"):
            print("Предупреждение: не удалось отправить карточку, шлем только текст:", res_photo)
    except Exception as e:
        print(f"Предупреждение: ошибка создания/отправки карточки Pillow ({e}), шлем только текст.")

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
