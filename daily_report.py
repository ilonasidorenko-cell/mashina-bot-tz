# -*- coding: utf-8 -*-
"""Ежедневный автоотчёт владельцу в Telegram."""
import os
import subprocess

import bot

def main():
    up = subprocess.run(["uptime"], capture_output=True, text=True).stdout.strip()
    st = subprocess.run(["systemctl", "is-active", "mashina-bot"], capture_output=True, text=True).stdout.strip()
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "failover.log")
    try:
        tail = "\n".join(open(log_path).read().strip().split("\n")[-3:])
    except Exception:
        tail = "лог пуст"
    text = "Ежедневный отчёт:\nUptime: " + up + "\nСервис: " + st + "\nПоследние строки лога:\n" + tail
    owner = os.environ.get("ALERT_CHAT_ID", "")
    if owner:
        bot.send(owner, text)

if __name__ == "__main__":
    main()
