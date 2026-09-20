# -*- coding: utf-8 -*-
"""
watchdog.py — сторож контура.

Раз в запуск делает живой вызов модели и, если ответа нет, пишет в лог и
сообщает вам в Telegram. Запускается таймером systemd раз в 10 минут.
Смысл простой: контур считается рабочим не тогда, когда сервис active,
а тогда, когда он отвечает.
"""
import os

import llm

ALERT_CHAT = os.environ.get("ALERT_CHAT_ID", "")


def notify(text):
    if not ALERT_CHAT:
        return
    import bot
    bot.send(ALERT_CHAT, text)


def main():
    try:
        answer, who = llm.ask("Ответь одним словом: ОК")
        llm.log(f"сторож: контур жив, ответил {who}")
        if who != "cli":
            notify(f"Основной канал молчит, работаем с резерва: {who}")
    except Exception as e:
        llm.log(f"сторож: контур мёртв: {e}")
        notify(f"Контур не отвечает ни по одному каналу: {e}")


if __name__ == "__main__":
    main()
