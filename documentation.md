# Документация: Telegram-бот студии навесных потолков

## 1. Назначение
Бот для первичного контакта с клиентами студии навесных потолков. Принимает заявки круглосуточно, квалифицирует клиента (4 вопроса), создаёт карточку в Trello, уведомляет менеджера. Голосовые расшифровываются автоматически.

## 2. Архитектура
Клиент (Telegram) -> Бот (bot.py) -> Trello (карточка) + Telegram (уведомление)
Голосовые -> Whisper (Groq) -> расшифровка в карточку.
Стек: Python 3.12, Telegram Bot API, Trello API, Groq Whisper, systemd.

## 3. Компоненты
- bot.py — Telegram-бот: квалификация, уведомления, расшифровка голосовых
- dialog.py — управление состоянием диалога
- llm.py — канал к моделям с резервной цепочкой
- watchdog.py — сторож: живой вызов модели
- lead_server.py — мини-воронка (форма -> Trello -> Telegram)
- daily_report.py — ежедневный автоотчёт

## 4. Systemd
- mashina-bot.service — основной бот, Restart=always
- mashina-watchdog.timer — сторож раз в 10 минут
- mashina-report.timer — ежедневный отчёт
Автозапуск: systemctl enable mashina-bot mashina-watchdog.timer mashina-report.timer

## 5. Сценарий работы
1. Клиент пишет /start -> бот здоровается и задаёт первый вопрос.
2. Клиент отвечает на 4 вопроса: имя, телефон, тип потолка, площадь.
3. Можно отвечать голосом — Whisper расшифровывает.
4. После последнего ответа бот создаёт карточку в Trello с полной перепиской, уведомляет менеджера, отвечает клиенту.

## 6. Резервная цепочка LLM
Порядок провайдеров в llm.py:
1. ollama — qwen2.5:1.5b
2. ollama_small — qwen2.5:0.5b
3. router — cheaprouter
4. groq — Groq (openai/gpt-oss-20b)
5. kie — Kie (/claude/v1/messages)
При падении основного канала система автоматически переключается на следующий. Лог — failover.log.

## 7. Развёртывание
apt install -y python3 python3-venv ffmpeg git
cd /root && git clone <repo> mashina_prodazh_uchebnaya
cd mashina_prodazh_uchebnaya && python3 -m venv venv
mkdir -p /etc/solaris && cp .env.example /etc/solaris/llm.env
nano /etc/solaris/llm.env
chmod 600 /etc/solaris/llm.env
cp systemd/*.service systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now mashina-bot mashina-watchdog.timer

## 8. Мониторинг
- systemctl status mashina-bot
- tail -20 failover.log
- venv/bin/python llm.py (РЕЗЕРВ ОК)
- /резерв в боте
- /отчёт в боте

## 9. Восстановление после сбоя
nohup /root/.local/bin/fcc-server > /root/fcc.log 2>&1 &
systemctl status mashina-bot ollama
systemctl restart mashina-bot
journalctl -u mashina-bot -n 30 --no-pager

## 10. Доступы
VPS: Hostkey, Нидерланды, Ubuntu 24.04
Секреты: /etc/solaris/llm.env (chmod 600)
Trello: доска Solaris, список «Нужно сделать»
Репозиторий: /root/mashina_prodazh_uchebnaya
