"""Отвечает на сообщения с датой: '21.10', '21.10.2026', 'сегодня', 'завтра', 'послезавтра'.
Запускается по расписанию (каждые ~5 минут) из GitHub Actions: забирает новые сообщения,
отвечает и помечает их прочитанными, поэтому хранить состояние не нужно.
"""
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

import notify

TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = str(os.environ["CHAT_ID"])
API = f"https://api.telegram.org/bot{TOKEN}"

HELP = (
    "Напиши дату, и я пришлю расписание на этот день:\n"
    "21.10 · 21.10.2026 · сегодня · завтра · послезавтра"
)
WORDS = {"сегодня": 0, "today": 0, "завтра": 1, "tomorrow": 1, "послезавтра": 2, "вчера": -1}


def tg(method: str, **params) -> dict:
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{API}/{method}", data=data)
    with urllib.request.urlopen(req, timeout=30) as r:
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
    if text.strip().lower().startswith("/start") or text.strip().lower() == "/help":
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
    updates = tg("getUpdates", timeout=0).get("result", [])
    if not updates:
        return
    for u in updates:
        msg = u.get("message") or {}
        if str(msg.get("chat", {}).get("id")) != CHAT_ID or not msg.get("text"):
            continue  # отвечаем только владельцу
        tg("sendMessage", chat_id=CHAT_ID, text=answer(msg["text"]))
    # помечаем всё как прочитанное, чтобы не отвечать дважды
    tg("getUpdates", offset=updates[-1]["update_id"] + 1, limit=1, timeout=0)


if __name__ == "__main__":
    main()
