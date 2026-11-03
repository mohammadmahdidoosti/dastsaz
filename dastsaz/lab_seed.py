"""The first designs to test, ready in the lab before the booth opens, so the owner only types the numbers.
Same list as the supplier brief (12 + 1 control) plus two men's designs (Twitter: boyfriends' birthday gifts)."""
from __future__ import annotations

from . import lab

DESIGNS = [  # name, Basalam search, typical selling price (toman), tags, control
    ("گردنبند استیل ساده با آویز کوچک (مرجع)", "گردنبند استیل", 145000, "گردنبند,استیل,مرجع", True),
    ("دستبند تنیسی", "دستبند تنیسی", 81000, "دستبند,نگین,رو به اوج", False),
    ("گوشواره ستاره", "گوشواره ستاره", 148000, "گوشواره,ستاره,کم‌رقیب", False),
    ("گردنبند گل چهارپر", "گردنبند گل چهارپر", 307000, "گردنبند,گل چهارپر", False),
    ("دستبند گل چهارپر", "دستبند گل چهارپر", 229000, "دستبند,گل چهارپر", False),
    ("گردنبند ماه و آسمان شب", "گردنبند آسمان شب", 136000, "گردنبند,ماه,شب‌تاب", False),
    ("دستبند بنگل", "دستبند بنگل", 203000, "دستبند,بنگل", False),
    ("گردنبند مروارید روی زنجیر استیل", "گردنبند مروارید", None, "گردنبند,مروارید", False),
    ("گردنبند اسم و حروف (حک لیزری)", "گردنبند اسم", None, "گردنبند,اسم,شخصی‌سازی,کادو", False),
    ("دستبند اسم لاتین", "دستبند اسم لاتین", None, "دستبند,اسم,شخصی‌سازی,کادو", False),
    ("انگشتر استیل رنگ‌ثابت", "انگشتر استیل", None, "انگشتر,استیل", False),
    ("گوشواره گل و برگ", "گوشواره گل و برگ", 153000, "گوشواره,گل", False),
    ("ست کادویی گردنبند و دستبند در جعبه", "ست گردنبند و دستبند", None, "ست,کادو,بسته‌بندی", False),
    ("دستبند چرم مردانه با پلاک اسم", "دستبند چرم مردانه", None, "مردانه,دستبند,چرم,اسم,کادو", False),
    ("زنجیر استیل مردانه", "زنجیر مردانه", None, "مردانه,زنجیر,استیل", False),
]


def seed(channel: str = "basalam") -> int:
    """Adds the designs that are not in the lab yet (by name). Returns how many were added."""
    have = {t["name"] for t in lab.load()}
    n = 0
    for name, q, price, tags, control in DESIGNS:
        if name in have:
            continue
        lab.add(name, channel, "report", price=price, query=q, stage="pretest", control=control,
                note="از بریف تأمین‌کننده", tags=tags)
        n += 1
    return n
