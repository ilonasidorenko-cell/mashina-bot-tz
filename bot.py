# -*- coding: utf-8 -*-
"""
bot.py — минимальный Telegram-бот учебной сборки «Машина продаж».

Задача этого файла: показать скелет, который переживает перезагрузку сервера
и смерть основного канала к моделям. Ничего лишнего, только стандартная
библиотека, чтобы не отвлекаться на зависимости.

Команды:
  /start   — приветствие
  /резерв  — проверка контура, печатает «РЕЗЕРВ ОК», если живых звеньев два и больше
любой другой текст уходит в модель через llm.ask
"""
import json
import os
import time
import urllib.parse
import urllib.request

import llm

TOKEN = os.environ.get("TG_BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{TOKEN}"
SYSTEM = os.environ.get("BOT_SYSTEM", "Ты ассистент. Отвечай коротко, по делу, на русском.")
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")


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
    if not text:
        send(chat_id, "Пришлите текстом.")
        return
    if text.startswith("/start"):
        send(chat_id, "Бот на связи. Напишите вопрос, отвечу через модель. "
                      "Команда /резерв проверит цепочку каналов.")
        return
    if text.startswith("/отчёт") or text.startswith("/report"):
        import subprocess
        up = subprocess.run(["uptime"], capture_output=True, text=True).stdout.strip()
        st = subprocess.run(["systemctl", "is-active", "mashina-bot"], capture_output=True, text=True).stdout.strip()
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "failover.log")
        try:
            tail = "\n".join(open(log_path).read().strip().split("\n")[-3:])
        except Exception:
            tail = "лог пуст"
        send(chat_id, "Отчёт:\nUptime: " + up + "\nСервис: " + st + "\nПоследние строки лога:\n" + tail)
        return
    if text.startswith("/резерв") or text.startswith("/reserve"):
        ok = llm.selftest()
        send(chat_id, ("РЕЗЕРВ ОК\nЖивые звенья: " + ", ".join(ok)) if len(ok) >= 2
             else "РЕЗЕРВА НЕТ, живых звеньев меньше двух: " + (", ".join(ok) or "нет"))
        return
    try:
        answer, who = llm.ask(text, SYSTEM)
        send(chat_id, answer + (f"\n\n(ответ с резерва: {who})" if who != "cli" else ""))
    except Exception as e:
        send(chat_id, f"Не смог ответить: {e}")


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
