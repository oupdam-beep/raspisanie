"""Отправляет расписание на сегодня в Telegram. Запускается раз в день из GitHub Actions."""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
TZ = ZoneInfo(os.getenv("TZ_NAME", "Asia/Yekaterinburg"))

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]


def get_lessons(date: datetime) -> list:
    data = json.loads((Path(__file__).parent / "schedule.json").read_text(encoding="utf-8"))
    if "odd" in data or "even" in data:
        data = data["odd" if date.isocalendar().week % 2 else "even"]
    return data.get(DAYS[date.weekday()], [])


def format_day(date: datetime) -> str:
    lessons = get_lessons(date)
    title = f"📅 {DAYS_RU[date.weekday()]}, {date:%d.%m}"
    if not lessons:
        return f"{title}\n\nПар нет 🎉"
    lines = [title, ""]
    for i, l in enumerate(lessons, 1):
        room = f" — ауд. {l['room']}" if l.get("room") else ""
        teacher = f" ({l['teacher']})" if l.get("teacher") else ""
        lines.append(f"{i}. {l['time']}  {l['subject']}{teacher}{room}")
    return "\n".join(lines)


def send(text: str):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    body = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text}).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=30) as r:
        print(r.status, r.read().decode())


if __name__ == "__main__":
    send(format_day(datetime.now(TZ)))
