# -*- coding: utf-8 -*-
"""Квалификация клиента студии навесных потолков."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "dialogs.json")

QUESTIONS = [
    ("name", "Как вас зовут?"),
    ("phone", "Ваш телефон или Telegram для связи?"),
    ("ceiling_type", "Какой потолок интересует: матовый, глянцевый, сатин?"),
    ("area", "Примерная площадь потолка в квадратных метрах?"),
]


def load_state():
    try:
        return json.load(open(STATE_FILE))
    except Exception:
        return {}


def save_state(state):
    json.dump(state, open(STATE_FILE, "w"), ensure_ascii=False)


def get_dialog(chat_id):
    state = load_state()
    return state.get(str(chat_id))


def start_dialog(chat_id):
    state = load_state()
    state[str(chat_id)] = {"step": 0, "answers": {}, "history": []}
    save_state(state)


def add_message(chat_id, role, text):
    state = load_state()
    dialog = state.get(str(chat_id), {"step": 0, "answers": {}, "history": []})
    dialog["history"].append({"role": role, "text": text})
    state[str(chat_id)] = dialog
    save_state(state)


def process_answer(chat_id, text):
    """Возвращает (готово, следующий_вопрос)."""
    state = load_state()
    dialog = state.get(str(chat_id))
    if not dialog:
        return False, None
    step = dialog["step"]
    if step < len(QUESTIONS):
        key, _ = QUESTIONS[step]
        dialog["answers"][key] = text
        dialog["step"] = step + 1
        state[str(chat_id)] = dialog
        save_state(state)
    if dialog["step"] >= len(QUESTIONS):
        return True, None
    return False, QUESTIONS[dialog["step"]][1]


def clear_dialog(chat_id):
    state = load_state()
    state.pop(str(chat_id), None)
    save_state(state)


def get_answers(chat_id):
    dialog = get_dialog(chat_id)
    return dialog["answers"] if dialog else {}


def get_history(chat_id):
    dialog = get_dialog(chat_id)
    return dialog["history"] if dialog else []
