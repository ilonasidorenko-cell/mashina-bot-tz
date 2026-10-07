# -*- coding: utf-8 -*-
"""bot.py — Telegram-бот студии навесных потолков с квалификацией."""
import json
import os
import time
import urllib.parse
import urllib.request

import dialog
import llm

TOKEN = os.environ.get("TG_BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{TOKEN}"
SYSTEM = os.environ.get("BOT_SYSTEM", "Ты ассистент студии навесных потолков. Отвечай коротко, по делу, на русском.")
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")

TRELLO_KEY = os.environ.get("TRELLO_KEY", "")
TRELLO_TOKEN = os.environ.get("TRELLO_TOKEN", "")
TRELLO_LIST_ID = os.environ.get("TRELLO_LIST_ID", "")


def api(method, **params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{API}/{method}", data=data)
    try:
        with urllib.request.urlopen(req, timeout=35) as r:
            return json.loads(r.read())
    except Exception as e:
        llm.log(f"telegram {method}: {e}")
        return {}


def send(chat_id, text):
    api("sendMessage", chat_id=chat_id, text=text[:4000])


def send_voice(chat_id, voice_file_id):
    """Скачивает голосовое и расшифровывает через Groq Whisper."""
    import subprocess
    import tempfile
    try:
        file_info = api("getFile", file_id=voice_file_id)
        if not file_info.get("ok"):
            return None
        file_path = file_info["result"]["file_path"]
        url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
        oga = tempfile.mktemp(suffix=".oga")
        mp3 = tempfile.mktemp(suffix=".mp3")
        urllib.request.urlretrieve(url, oga)
        subprocess.run(["ffmpeg", "-y", "-i", oga, "-ar", "16000", "-ac", "1", "-af", "volume=2.0", mp3], capture_output=True)
        groq_key = os.environ.get("GROQ_API_KEY", "")
        with open(mp3, "rb") as f:
            boundary = "----boundary"
            body = b""
            body += f"--{boundary}\r\n".encode()
            body += b'Content-Disposition: form-data; name="file"; filename="audio.mp3"\r\n'
            body += b"Content-Type: audio/mpeg\r\n\r\n"
            body += f.read() + b"\r\n"
            body += f"--{boundary}\r\n".encode()
            body += b'Content-Disposition: form-data; name="model"\r\n\r\n'
            body += b"whisper-large-v3\r\n"
            body += f"--{boundary}\r\n".encode()
            body += b'Content-Disposition: form-data; name="language"\r\n\r\n'
            body += b"ru\r\n"
            body += f"--{boundary}\r\n".encode()
            body += b'Content-Disposition: form-data; name="prompt"\r\n\r\n'
            body += "матовый глянцевый сатин потолок площадь".encode() + b"\r\n"
            body += f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            data=body,
            headers={"Authorization": f"Bearer {groq_key}",
                     "Content-Type": f"multipart/form-data; boundary={boundary}",
                     "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read())
        return result.get("text", "")
    except Exception as e:
        llm.log(f"whisper: {e}")
        return None


def create_trello_card(chat_id):
    """Создаёт карточку в Trello с полной перепиской."""
    answers = dialog.get_answers(chat_id)
    history = dialog.get_history(chat_id)
    name = answers.get("name", "Без имени")
    desc = (
        f"Телефон: {answers.get('phone', '-')}\n"
        f"Тип потолка: {answers.get('ceiling_type', '-')}\n"
        f"Площадь: {answers.get('area', '-')}\n\n"
        "--- Переписка ---\n" +
        "\n".join(f"{m['role']}: {m['text']}" for m in history)
    )
    params = urllib.parse.urlencode({
        "key": TRELLO_KEY, "token": TRELLO_TOKEN,
        "idList": TRELLO_LIST_ID, "name": f"Лид: {name}", "desc": desc,
    })
    url = f"https://api.trello.com/1/cards?{params}"
    req = urllib.request.Request(url, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def notify_manager(chat_id):
    answers = dialog.get_answers(chat_id)
    owner = os.environ.get("ALERT_CHAT_ID", "")
    if owner:
        send(owner, f"Новый лид!\nИмя: {answers.get('name', '-')}\n"
                    f"Телефон: {answers.get('phone', '-')}\n"
                    f"Тип: {answers.get('ceiling_type', '-')}\n"
                    f"Площадь: {answers.get('area', '-')}")


def load_offset():
    try:
        return json.load(open(STATE)).get("offset", 0)
    except Exception:
        return 0


def save_offset(v):
    json.dump({"offset": v}, open(STATE, "w"))


def handle(msg):
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    voice = msg.get("voice")

    if text.startswith("/start"):
        dialog.start_dialog(chat_id)
        dialog.add_message(chat_id, "bot", "Здравствуйте! Я помогу рассчитать потолок. Как вас зовут?")
        send(chat_id, "Здравствуйте! Я помогу рассчитать потолок.\n\nКак вас зовут?")
        return

    if text.startswith("/резерв"):
        ok = llm.selftest()
        send(chat_id, ("РЕЗЕРВ ОК\nЖивые звенья: " + ", ".join(ok)) if len(ok) >= 2
             else "РЕЗЕРВА НЕТ: " + (", ".join(ok) or "нет"))
        return

    if text.startswith("/отчёт"):
        import subprocess
        up = subprocess.run(["uptime"], capture_output=True, text=True).stdout.strip()
        st = subprocess.run(["systemctl", "is-active", "mashina-bot"], capture_output=True, text=True).stdout.strip()
        send(chat_id, f"Отчёт:\nUptime: {up}\nСервис: {st}")
        return

    if voice:
        transcribed = send_voice(chat_id, voice["file_id"])
        if transcribed:
            text = transcribed
            send(chat_id, f"(расшифровано: {text})")
        else:
            send(chat_id, "Не смог расшифровать голосовое, напишите текстом.")
            return

    if not text:
        send(chat_id, "Пришлите текстом или голосовым.")
        return

    dialog.add_message(chat_id, "client", text)
    done, next_q = dialog.process_answer(chat_id, text)
    if done:
        try:
            create_trello_card(chat_id)
            notify_manager(chat_id)
            send(chat_id, "Спасибо! Заявка принята, менеджер свяжется с вами в течение часа.")
        except Exception as e:
            llm.log(f"ошибка лида: {e}")
            send(chat_id, "Заявка принята, но что-то пошло не так. Менеджер свяжется.")
        dialog.clear_dialog(chat_id)
    else:
        dialog.add_message(chat_id, "bot", next_q)
        send(chat_id, next_q)


def main():
    if not TOKEN:
        raise SystemExit("нет TG_BOT_TOKEN в окружении")
    llm.log("бот запущен")
    offset = load_offset()
    while True:
        r = api("getUpdates", offset=offset + 1, timeout=25)
        for upd in r.get("result", []):
            offset = upd["update_id"]
            save_offset(offset)
            if "message" in upd:
                try:
                    handle(upd["message"])
                except Exception as e:
                    llm.log(f"обработка сообщения: {e}")
        time.sleep(1)


if __name__ == "__main__":
    main()
