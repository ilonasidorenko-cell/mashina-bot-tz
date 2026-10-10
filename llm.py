# -*- coding: utf-8 -*-
"""
llm.py — канал к моделям с резервом.

Логика простая и та же, что в боевом контуре Solaris:
  1) основной канал: официальный CLI Claude Code (`claude -p`), он работает
     и на подписке, и на ключе роутера, смотря как вы его настроили;
  2) если основной молчит или вернул ошибку, идём по резервной цепочке
     провайдеров, совместимых с OpenAI: роутер, Groq, DeepSeek;
  3) каждое переключение пишем строкой в failover.log. Эта строка и есть
     доказательство для домашки модуля 2.

Ключи берём из окружения, в коде их нет и быть не должно.
"""
import json
import os
import subprocess
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "failover.log")
CLI = os.environ.get("CLAUDE_CLI", "claude")
MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5")

# Резервная цепочка. Порядок сверху вниз, отключить звено можно, убрав ключ из .env.
PROVIDERS = [
    {"name": "ollama", "url": "http://127.0.0.1:11434/v1/chat/completions",
     "key": "OLLAMA_DUMMY", "model": "qwen2.5:1.5b"},
    {"name": "ollama_small", "url": "http://127.0.0.1:11434/v1/chat/completions",
     "key": "OLLAMA_DUMMY", "model": "qwen2.5:0.5b"},
    # Роутер говорит нативным форматом Anthropic (/v1/messages, ключ в x-api-key),
    # остальные вендоры — форматом OpenAI (/chat/completions, ключ в Authorization).
    # Имена моделей у роутера голые, датированные он не знает и отдаёт 404.
    {"name": "router", "url": "https://router.cheap/v1/messages", "anthropic": True,
     "key": "ANTHROPIC_API_KEY", "model": os.environ.get("ROUTER_MODEL", "claude-sonnet-4-6")},
    {"name": "groq", "url": "https://api.groq.com/openai/v1/chat/completions",
     "key": "GROQ_API_KEY", "model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")},
#    {"name": "deepseek", "url": "https://api.deepseek.com/chat/completions",
#     "key": "DEEPSEEK_API_KEY", "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")},
#    {"name": "openrouter", "url": "https://openrouter.ai/api/v1/chat/completions",
#     "key": "OPENROUTER_API_KEY", "model": "meta-llama/llama-3.3-70b-instruct:free"},
#    {"name": "cerebras", "url": "https://api.cerebras.ai/v1/chat/completions",
#     "key": "CEREBRAS_API_KEY", "model": "llama3.1-8b"},
    {"name": "kie", "url": "https://api.kie.ai/claude/v1/messages", "anthropic": True,
     "key": "KIE_AI_API_KEY", "model": "claude-sonnet-4-6"},
]


def log(line):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{stamp} {line}\n")
    print(f"{stamp} {line}", flush=True)


def ask_cli(prompt, timeout=120):
    """Основной канал: официальный CLI Claude Code."""
    r = subprocess.run([CLI, "-p", prompt, "--model", MODEL, "--output-format", "text"],
                       capture_output=True, text=True, timeout=timeout)
    out = (r.stdout or "").strip()
    if r.returncode != 0 or not out:
        raise RuntimeError((r.stderr or "пустой ответ CLI").strip()[:200])
    return out


def ask_http(p, prompt, system, timeout=10):
    """Одно звено резерва. Формат запроса общий для всех трёх вендоров."""
    key = os.environ.get(p["key"])
    if not key:
        raise RuntimeError(f"нет ключа {p['key']}")
    if p.get("anthropic"):
        payload = {"model": p["model"], "max_tokens": 1200,
                   "messages": [{"role": "user", "content": prompt}]}
        if system:
            payload["system"] = system
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01",
                   "Content-Type": "application/json"}
    else:
        payload = {"model": p["model"], "max_tokens": 1200,
                   "messages": ([{"role": "system", "content": system}] if system else [])
                               + [{"role": "user", "content": prompt}]}
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    req = urllib.request.Request(p["url"], data=json.dumps(payload).encode(), headers=headers)
    req.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64)")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read())
    if p.get("anthropic"):
        return "".join(b.get("text", "") for b in j.get("content", [])).strip()
    return j["choices"][0]["message"]["content"].strip()


def ask(prompt, system=""):
    """Возвращает (ответ, кто ответил). Бросает исключение, только если умерли все."""
    try:
        return ask_cli(prompt), "cli"
    except Exception as e:
        log(f"ПЕРЕКЛЮЧЕНИЕ: основной канал (CLI) недоступен: {e}")

    for p in PROVIDERS:
        try:
            out = ask_http(p, prompt, system)
            log(f"ОТВЕТ С РЕЗЕРВА: {p['name']} ({p['model']})")
            return out, p["name"]
        except Exception as e:
            log(f"резерв {p['name']} не ответил: {e}")

    log("ВСЯ ЦЕПОЧКА МОЛЧИТ")
    raise RuntimeError("все каналы недоступны")


def selftest():
    """Проверка контура: спрашиваем каждое звено и печатаем, кто живой."""
    ok = []
    try:
        ask_cli("Ответь одним словом: ОК", timeout=10)
        ok.append("cli")
    except Exception as e:
        print(f"cli: {e}")
    for p in PROVIDERS:
        try:
            ask_http(p, "Ответь одним словом: ОК", "")
            ok.append(p["name"])
        except Exception as e:
            print(f"{p['name']}: {e}")
    print("РЕЗЕРВ ОК" if len(ok) >= 2 else "РЕЗЕРВА НЕТ", "| живые звенья:", ", ".join(ok) or "нет")
    return ok


if __name__ == "__main__":
    selftest()
