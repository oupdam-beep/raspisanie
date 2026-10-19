"""Отвечает на сообщения с датой: '21.10', '21.10.2026', 'сегодня', 'завтра', 'послезавтра'.

Каждый запуск из GitHub Actions живёт ~4,5 минуты и постоянно слушает Telegram (long polling),
поэтому ответ приходит за секунды. Запуски идут встык (cron каждые 5 минут).
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

import notify

TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = str(os.environ["CHAT_ID"])
API = f"https://api.telegram.org/bot{TOKEN}"
LOOP_SECONDS = int(os.getenv("LOOP_SECONDS", "270"))  # сколько секунд слушать
POLL_TIMEOUT = 20                                      # длина одного long-poll запроса

HELP = (
    "Напиши дату, и я пришлю расписание на этот день:\n"
    "21.10 · 21.10.2026 · сегодня · завтра · послезавтра"
)
WORDS = {"сегодня": 0, "today": 0, "завтра": 1, "tomorrow": 1, "послезавтра": 2, "вчера": -1}


def tg(method: str, **params) -> dict:
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{API}/{method}", data=data)
    with urllib.request.urlopen(req, timeout=POLL_TIMEOUT + 15) as r:
        return json.load(r)


def parse_date(text: str, now: datetime):
    t = text.strip().lower().lstrip("/")
    base = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if t in WORDS:
        return base + timedelta(days=WORDS[t])
    m = re.search(r"(\d{1,2})[./\-](\d{1,2})(?:[./\-](\d{2,4}))?", t)
    if not m:
        return None
    day, month, year = int(m[1]), int(m[2]), m[3]
    if year:
        year = int(year) + 2000 if len(year) == 2 else int(year)
    else:
        year = base.year
    try:
        return base.replace(year=year, month=month, day=day)
    except ValueError:
        return None


def answer(text: str) -> str:
    now = datetime.now(notify.TZ)
    low = text.strip().lower()
    if low.startswith("/start") or low == "/help":
        return HELP
    date = parse_date(text, now)
    if date is None:
        return HELP
    try:
        lessons = notify.fetch_from_site(date) if notify.SCHEDULE_URL else notify.fetch_from_file(date)
    except Exception as e:
        return f"⚠️ Не удалось получить расписание: {e}"
    return notify.format_day(date, lessons)


def main():
    end = time.time() + LOOP_SECONDS
    offset = None
    while time.time() < end:
        wait = max(0, min(POLL_TIMEOUT, int(end - time.time())))
        params = {"timeout": wait}
        if offset is not None:
            params["offset"] = offset
        try:
            updates = tg("getUpdates", **params).get("result", [])
        except Exception as e:  # сеть моргнула, пробуем снова
            print("poll error:", e)
            time.sleep(3)
            continue
        for u in updates:
            offset = u["update_id"] + 1
            msg = u.get("message") or {}
            if str(msg.get("chat", {}).get("id")) != CHAT_ID or not msg.get("text"):
                continue  # отвечаем только владельцу
            try:
                tg("sendMessage", chat_id=CHAT_ID, text=answer(msg["text"]))
            except Exception as e:
                print("send error:", e)
    if offset is not None:  # подтверждаем прочитанное, чтобы следующий запуск не ответил повторно
        try:
            tg("getUpdates", offset=offset, limit=1, timeout=0)
        except Exception as e:
            print("confirm error:", e)


if __name__ == "__main__":
    main()
