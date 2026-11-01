"""Gift occasions in Iran for the coming months: solar ones on fixed Persian dates, religious ones on the lunar
calendar (Umm al-Qura via hijridate; Iran's official date can differ by a day, so they are marked approximate).
Each comes with the order-by date (4 weeks before) and the themes that sell, matched to this week's test list.
Muharram and Safar are marked as a quiet season for festive jewelry."""
from __future__ import annotations

import datetime as dt

ORDER_DAYS = 28

# (name, jalali month, day, themes)
SOLAR = [
    ("شب یلدا", 9, 30, ["قرمز", "انار", "هندوانه", "ست", "یاقوت"]),
    ("ولنتاین", 11, 25, ["قلب", "اسم", "ست", "زوج", "قرمز"]),
    ("سپندارمذگان (روز عشق ایرانی)", 11, 29, ["قلب", "اسم", "ست", "زوج"]),
    ("نوروز", 1, 1, ["فیروزه", "گل", "سکه", "سبز", "ماهی"]),
    ("روز طبیعت (سیزده‌بدر)", 1, 13, ["گل", "برگ", "پروانه", "طبیعت"]),
]
# (name, hijri month, day, themes)
LUNAR = [
    ("روز مادر و روز زن", 6, 20, ["اسم", "سنگ تولد", "قلب", "ست", "شخصی"]),
    ("روز پدر و روز مرد", 7, 13, ["مردانه", "چرم"]),
    ("روز دختر", 11, 1, ["اسم", "ظریف", "قلب", "پروانه", "ستاره"]),
]
QUIET = ("محرم و صفر (فصل کم‌فروش جواهر جشن)", 1, 1, 2, 29)


def j2g(jy: int, jm: int, jd: int) -> dt.date:
    """Persian (Jalali) date -> Gregorian date (standard arithmetic)."""
    jy += 1595
    days = -355668 + 365 * jy + (jy // 33) * 8 + ((jy % 33) + 3) // 4 + jd
    days += (jm - 1) * 31 if jm < 7 else (jm - 7) * 30 + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0
    for gm, ml in enumerate([31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31], 1):
        if gd <= ml:
            return dt.date(gy, gm, gd)
        gd -= ml
    raise ValueError("bad date")


def _jalali_year(d: dt.date) -> int:
    return d.year - 621 if (d.month, d.day) >= (3, 21) else d.year - 622


def _hijri(hy: int, hm: int, hd: int) -> dt.date | None:
    try:
        from hijridate import Hijri
        g = Hijri(hy, hm, hd).to_gregorian()
        return dt.date(g.year, g.month, g.day)
    except Exception:  # noqa: BLE001
        return None


def _matches(t: dict, themes: list[str]) -> bool:
    """Whole-word match (so «ست» is not found inside «دستبند»); a theme of two words must appear as a phrase."""
    words = f" {t['q']} {t.get('name') or ''} ".replace("\u200c", " ")
    return any(f" {th} " in words for th in themes)


def upcoming(today: dt.date | None = None, days: int = 150, test_list: list[dict] | None = None) -> list[dict]:
    today = today or dt.date.today()
    end = today + dt.timedelta(days=days)
    out = []
    jy = _jalali_year(today)
    for name, m, d, themes in SOLAR:
        for y in (jy, jy + 1):
            g = j2g(y, m, d)
            if today <= g <= end:
                out.append({"name": name, "date": g.isoformat(), "approx": False, "themes": themes})
    try:
        from hijridate import Gregorian
        hy = Gregorian(today.year, today.month, today.day).to_hijri().year
    except Exception:  # noqa: BLE001
        hy = None
    if hy:
        for name, m, d, themes in LUNAR:
            for y in (hy, hy + 1):
                g = _hijri(y, m, d)
                if g and today <= g <= end:
                    out.append({"name": name, "date": g.isoformat(), "approx": True, "themes": themes})
        for y in (hy, hy + 1):
            a, b = _hijri(y, QUIET[1], QUIET[2]), _hijri(y, QUIET[3], QUIET[4])
            if a and b and a <= end and b >= today:
                out.append({"name": QUIET[0], "date": a.isoformat(), "until": b.isoformat(), "approx": True,
                            "themes": [], "quiet": True})
    for o in out:
        g = dt.date.fromisoformat(o["date"])
        o["days_left"] = (g - today).days
        ob = g - dt.timedelta(days=ORDER_DAYS)
        o["order_by"] = ob.isoformat() if ob >= today else ""
        o["designs"] = [t.get("name") or t["q"] for t in (test_list or []) if _matches(t, o["themes"])][:4]
    return sorted(out, key=lambda o: o["date"])
