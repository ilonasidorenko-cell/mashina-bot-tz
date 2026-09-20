# -*- coding: utf-8 -*-
"""Мини-воронка: форма -> Trello -> Telegram."""
import json
import os
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

import bot
import llm

TRELLO_KEY = os.environ.get("TRELLO_KEY", "")
TRELLO_TOKEN = os.environ.get("TRELLO_TOKEN", "")
TRELLO_LIST_ID = os.environ.get("TRELLO_LIST_ID", "")
OWNER = os.environ.get("ALERT_CHAT_ID", "")

PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>ИИ-ассистент для салона</title>
<style>body{font-family:sans-serif;max-width:600px;margin:60px auto;padding:20px}
input,textarea{width:100%;padding:10px;margin:6px 0;box-sizing:border-box}
button{background:#0ea5e9;color:#fff;border:0;padding:12px 24px;cursor:pointer}</style>
</head><body>
<h1>ИИ-ассистент для салона красоты</h1>
<p>Отвечает клиентам в Telegram 24/7, записывает на услуги, напоминает о визите.</p>
<form method="POST" action="/lead">
<input name="name" placeholder="Ваше имя" required>
<input name="contact" placeholder="Телефон или Telegram" required>
<textarea name="comment" placeholder="Задача или вопрос"></textarea>
<button type="submit">Оставить заявку</button>
</form></body></html>"""

THANKS = """<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body><h1>Спасибо! Заявка принята.</h1><p>Вернёмся в течение часа.</p></body></html>"""


def create_card(name, contact, comment, source):
    desc = "Контакт: " + contact + "\\nКомментарий: " + comment + "\\nИсточник: " + source
    params = urllib.parse.urlencode({
        "key": TRELLO_KEY, "token": TRELLO_TOKEN,
        "idList": TRELLO_LIST_ID, "name": "Лид: " + name, "desc": desc,
    })
    url = "https://api.trello.com/1/cards?" + params
    req = urllib.request.Request(url, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def notify_owner(name, contact, comment, source):
    if OWNER:
        bot.send(OWNER, "Новый лид!\\nИмя: " + name + "\\nКонтакт: " + contact +
                         "\\nКомментарий: " + comment + "\\nИсточник: " + source)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE.encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()
        data = urllib.parse.parse_qs(body)
        name = data.get("name", [""])[0]
        contact = data.get("contact", [""])[0]
        comment = data.get("comment", [""])[0]
        source = self.headers.get("Referer", "прямой заход")
        try:
            create_card(name, contact, comment, source)
            notify_owner(name, contact, comment, source)
            llm.log("лид обработан: " + name)
        except Exception as e:
            llm.log("ошибка лида: " + str(e))
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(THANKS.encode())

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8090), Handler).serve_forever()

