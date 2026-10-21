import os
import requests

MAX_API = os.environ.get("MAX_API_BASE", "https://platform-api2.max.ru")


def upload_image(token, path):
    r = requests.post(
        f"{MAX_API}/uploads",
        params={"type": "image"},
        headers={"Authorization": token},
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    upload_url = data.get("url")
    media_token = data.get("token")
    if not upload_url:
        raise RuntimeError("MAX не вернул URL для загрузки изображения")

    if path.startswith("http://") or path.startswith("https://"):
        content = requests.get(path, timeout=120).content
        filename = os.path.basename(path.split("?")[0]) or "image.jpg"
        files = {"data": (filename, content, "image/jpeg")}
    else:
        files = {"data": (os.path.basename(path), open(path, "rb"), "image/jpeg")}

    up = requests.post(upload_url, headers={"Authorization": token}, files=files, timeout=180)
    up.raise_for_status()

    if not media_token:
        try:
            payload = up.json()
            media_token = payload.get("token")
            photos = payload.get("photos") or {}
            if not media_token and photos:
                first = list(photos.values())[0]
                media_token = first.get("token") if isinstance(first, dict) else first
        except ValueError:
            pass

    if not media_token:
        raise RuntimeError("MAX не вернул токен изображения")
    return media_token


def publish_to_max(text, image_path=None, token=None, chat_id=None):
    token = token or os.environ.get("MAX_BOT_TOKEN")
    chat_id = chat_id or os.environ.get("MAX_CHANNEL_ID")
    if not token or not chat_id:
        print("MAX: нет MAX_BOT_TOKEN/MAX_CHANNEL_ID — публикация в MAX пропущена.")
        return None

    body = {"text": text, "format": "html", "notify": True}

    if image_path:
        try:
            media_token = upload_image(token, image_path)
            body["attachments"] = [{"type": "image", "payload": {"token": media_token}}]
        except Exception as e:
            print("Предупреждение: не удалось прикрепить изображение в MAX:", e)

    r = requests.post(
        f"{MAX_API}/messages",
        params={"chat_id": chat_id},
        headers={"Authorization": token, "Content-Type": "application/json"},
        json=body,
        timeout=90,
    )
    r.raise_for_status()
    print("Опубликовано в MAX:", r.json().get("message", {}).get("body", {}).get("text", "")[:80])
    return r.json()
