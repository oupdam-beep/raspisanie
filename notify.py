"""Отправляет расписание на сегодня в Telegram. Запускается раз в день из GitHub Actions.

Источник расписания:
  * SCHEDULE_URL задан  -> JSON с сайта колледжа (в URL можно использовать {date} = YYYY-MM-DD)
  * SCHEDULE_URL пуст   -> запасной вариант, локальный schedule.json
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.getenv("TZ_NAME", "Asia/Yekaterinburg"))
SCHEDULE_URL = os.getenv("SCHEDULE_URL", "").strip()
DRY_RUN = os.getenv("DRY_RUN") == "1"

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]


def clean(s: str) -> str:
    """Убирает пометку ' (в)' в конце."""
    return re.sub(r"\s*\(в\)\s*$", "", s or "").strip()


def names(items) -> str:
    return ", ".join(clean(i.get("name", "")) for i in (items or []) if i.get("name"))


def fetch_from_site(date: datetime) -> list:
    url = SCHEDULE_URL.replace("{date}", date.strftime("%Y-%m-%d"))
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if isinstance(data, dict):  # на случай, если список лежит внутри объекта
        data = next((v for v in data.values() if isinstance(v, list)), [])
    day = date.strftime("%Y-%m-%d")
    lessons = []
    for x in data:
        if x.get("date") != day:
            continue
        call = x.get("call") or {}
        lessons.append({
            "n": call.get("time", 0),
            "start": call.get("timeStart", ""),
            "end": call.get("timeEnd", ""),
            "subject": x.get("subject", ""),
            "subgroup": x.get("subgroup", 0),
            "teacher": names(x.get("teachers")),
            "room": names(x.get("auditories")),
        })
    return sorted(lessons, key=lambda l: l["n"])


def fetch_from_file(date: datetime) -> list:
    data = json.loads((Path(__file__).parent / "schedule.json").read_text(encoding="utf-8"))
    if "odd" in data or "even" in data:
        data = data["odd" if date.isocalendar().week % 2 else "even"]
    out = []
    for i, l in enumerate(data.get(DAYS[date.weekday()], []), 1):
        start, _, end = l["time"].partition("-")
        out.append({"n": i, "start": start, "end": end, "subject": l["subject"],
                    "subgroup": 0, "teacher": l.get("teacher", ""), "room": l.get("room", "")})
    return out


def format_day(date: datetime, lessons: list) -> str:
    title = f"📅 {DAYS_RU[date.weekday()]}, {date:%d.%m}"
    if not lessons:
        return f"{title}\n\nПар нет 🎉"
    lines = [title, ""]
    for l in lessons:
        lines.append(f"{l['n']}. {l['start']}–{l['end']}  {l['subject']}")
        details = []
        if l["subgroup"]:
            details.append(f"подгруппа {l['subgroup']}")
        if l["teacher"]:
            details.append(l["teacher"])
        if l["room"]:
            details.append(f"ауд. {l['room']}")
        if details:
            lines.append("    " + " · ".join(details))
    return "\n".join(lines)


def send(text: str):
    if DRY_RUN:
        print(text)
        return
    token, chat_id = os.environ["BOT_TOKEN"], os.environ["CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=body), timeout=30) as r:
        print(r.status)


if __name__ == "__main__":
    fake = os.getenv("TODAY")  # для тестов: TODAY=2026-10-24
    today = datetime.strptime(fake, "%Y-%m-%d").replace(tzinfo=TZ) if fake else datetime.now(TZ)
    try:
        lessons = fetch_from_site(today) if SCHEDULE_URL else fetch_from_file(today)
    except Exception as e:  # сайт недоступен / поменялся формат
        send(f"⚠️ Не удалось получить расписание: {e}")
        sys.exit(1)
    send(format_day(today, lessons))
