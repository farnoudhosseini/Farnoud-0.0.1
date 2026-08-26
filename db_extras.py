# ایموجی پریمیوم، گزارش گروهی، تنظیمات منو

from __future__ import annotations
from typing import Optional, List, Dict, Any, Tuple
from database import get_sync_connection, get_setting_sync, set_setting_sync
import secrets
import string
import re
import html
import json


def ensure_extras_tables():
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS premium_emojis (
                id INT AUTO_INCREMENT PRIMARY KEY,
                code VARCHAR(64) NOT NULL UNIQUE,
                custom_emoji_id VARCHAR(64) NOT NULL,
                label VARCHAR(100) DEFAULT NULL,
                created_by BIGINT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            for k, v in [
                ("inline_main_menu", "0"),
                ("report_group_id", ""),
                ("report_topic_sales", ""),
                ("report_topic_charges", ""),
                ("report_topic_tickets", ""),
                ("report_topic_errors", ""),
                ("report_topic_backup", ""),
                ("hourly_global_enabled", "0"),
                ("menu_buttons_json", "[]"),
                ("menu_buttons_per_row", "3"),
                ("backup_interval_hours", "2"),
                ("optimize_interval_hours", "0"),
            ]:
                cur.execute(
                    "INSERT IGNORE INTO settings (`key`, `value`) VALUES (%s,%s)",
                    (k, v),
                )
            conn.commit()
    finally:
        conn.close()


# ---- ایموجی پریمیوم ----

def gen_premium_code() -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "p_" + "".join(secrets.choice(alphabet) for _ in range(8))


def add_premium_emoji(code: str, custom_emoji_id: str, label: str = None, created_by: int = None) -> bool:
    code = (code or "").strip()
    if not code.startswith("p_"):
        return False
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO premium_emojis (code, custom_emoji_id, label, created_by)
                   VALUES (%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE custom_emoji_id=VALUES(custom_emoji_id), label=VALUES(label)""",
                (code, str(custom_emoji_id).strip(), label, created_by),
            )
            conn.commit()
            return True
    except Exception:
        return False
    finally:
        conn.close()


def list_premium_emojis() -> list:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM premium_emojis ORDER BY id DESC")
            return cur.fetchall() or []
    finally:
        conn.close()


def get_premium_emoji(code: str) -> Optional[dict]:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM premium_emojis WHERE code=%s", (code.strip(),))
            return cur.fetchone()
    finally:
        conn.close()


def delete_premium_emoji(code: str) -> bool:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM premium_emojis WHERE code=%s", (code.strip(),))
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


_PREMIUM_CODE_RE = re.compile(r"p_[a-z0-9]{4,32}", re.I)


def apply_premium_emojis(text: str) -> str:
    """
    جایگزینی کدهای p_... با تگ HTML ایموجی سفارشی تلگرام.
    خروجی باید با parse_mode=HTML ارسال شود.
    پشتیبانی از: p_xxx  |  [p_xxx]  |  {{p_xxx}}  |  {{premium:p_xxx}}  |  <premium:p_xxx>
    """
    if not text:
        return text or ""
    emojis = list_premium_emojis()
    if not emojis:
        return text
    for e in sorted(emojis, key=lambda x: len(x["code"]), reverse=True):
        code = e["code"]
        eid = str(e["custom_emoji_id"])
        replacement = f'<tg-emoji emoji-id="{html.escape(eid, quote=True)}">✨</tg-emoji>'
        safe = re.escape(code)
        text = re.sub(r"\[\s*" + safe + r"\s*\]", replacement, text)
        text = re.sub(r"\{\{\s*(?:premium:)?" + safe + r"\s*\}\}", replacement, text)
        text = re.sub(r"<premium\s*:\s*" + safe + r"\s*>", replacement, text, flags=re.I)
        text = text.replace(code, replacement)
    return text


def extract_premium_from_label(label: str) -> Tuple[str, Optional[str]]:
    """
    از متن دکمه کد p_xxx را جدا می‌کند.
    خروجی: (متن_تمیز_بدون_کد, custom_emoji_id یا None)
    """
    if not label:
        return "", None
    match = _PREMIUM_CODE_RE.search(label)
    if not match:
        return label.strip(), None
    code = match.group(0)
    clean = _PREMIUM_CODE_RE.sub("", label)
    clean = re.sub(r"\s{2,}", " ", clean).strip()
    row = get_premium_emoji(code)
    eid = str(row["custom_emoji_id"]) if row else None
    return clean or "•", eid


def strip_premium_codes(text: str) -> str:
    """حذف کدهای p_ از متن (برای ReplyKeyboard که HTML ندارد)."""
    if not text:
        return text or ""
    text = _PREMIUM_CODE_RE.sub("", text)
    return re.sub(r"\s{2,}", " ", text).strip()


# ---- گزارش گروهی ----

def get_report_group() -> Optional[int]:
    raw = get_setting_sync("report_group_id", "")
    if not raw:
        return None
    try:
        return int(raw)
    except Exception:
        return None


def set_report_group(chat_id: int):
    set_setting_sync("report_group_id", str(chat_id))


def get_report_topic(kind: str) -> Optional[int]:
    """kind: sales | charges | tickets | errors | backup"""
    raw = get_setting_sync(f"report_topic_{kind}", "")
    if not raw:
        return None
    try:
        return int(raw)
    except Exception:
        return None


def set_report_topic(kind: str, topic_id: int):
    set_setting_sync(f"report_topic_{kind}", str(topic_id))


# ---- منوی اصلی ----
# color: blue→primary | green→success | red→danger | none→default
# row: شماره سطر (اختیاری، برای چیدمان آزاد)
# per_row: حداکثر دکمه در هر سطر (پیش‌فرض ۳)

COLOR_TO_STYLE = {
    "blue": "primary",
    "green": "success",
    "red": "danger",
    "primary": "primary",
    "success": "success",
    "danger": "danger",
    "none": None,
    "": None,
}

DEFAULT_MENU_BUTTONS = [
    {"key": "buy", "label": "🛒 خرید سرویس جدید", "callback": "menu_buy", "enabled": True, "color": "blue", "row": 0},
    {"key": "services", "label": "📱 سرویس‌های من", "callback": "menu_services", "enabled": True, "color": "blue", "row": 0},
    {"key": "wallet", "label": "💰 کیف پول من", "callback": "menu_wallet", "enabled": True, "color": "green", "row": 1},
    {"key": "trial", "label": "🎁 تست رایگان", "callback": "menu_trial", "enabled": True, "color": "blue", "row": 1},
    {"key": "support", "label": "🛠 پشتیبانی", "callback": "menu_support", "enabled": True, "color": "red", "row": 2},
    {"key": "education", "label": "📚 آموزش", "callback": "menu_education", "enabled": True, "color": "none", "row": 2},
    {"key": "reseller", "label": "🤝 درخواست نمایندگی", "callback": "menu_reseller", "enabled": True, "color": "none", "row": 3},
]


def get_menu_buttons() -> List[Dict[str, Any]]:
    raw = get_setting_sync("menu_buttons_json", "[]")
    try:
        data = json.loads(raw or "[]")
        if isinstance(data, list) and data:
            # نرمال‌سازی فیلدهای قدیمی
            out = []
            for i, x in enumerate(data):
                if not isinstance(x, dict):
                    continue
                item = dict(x)
                item.setdefault("key", f"btn_{i}")
                item.setdefault("label", item["key"])
                item.setdefault("callback", "menu_home")
                item.setdefault("enabled", True)
                item.setdefault("color", "none")
                if "row" not in item:
                    item["row"] = i // 3
                out.append(item)
            return out
    except Exception:
        pass
    return [dict(x) for x in DEFAULT_MENU_BUTTONS]


def set_menu_buttons(items):
    set_setting_sync("menu_buttons_json", json.dumps(items, ensure_ascii=False))
    # کیبوردهای کش‌شده باید فوراً invalidate شوند تا دکمه جدید/حذف‌شده
    # بدون نیاز به ری‌استارت در بات اعمال شود.
    try:
        from handlers.wallet import invalidate_main_keyboard_cache
        invalidate_main_keyboard_cache()
    except Exception:
        pass


def get_buttons_per_row() -> int:
    try:
        n = int(get_setting_sync("menu_buttons_per_row", "3") or "3")
        return max(1, min(n, 8))
    except Exception:
        return 3


def set_buttons_per_row(n: int):
    set_setting_sync("menu_buttons_per_row", str(max(1, min(int(n), 8))))


def build_menu_rows(items: Optional[List[Dict]] = None, per_row: Optional[int] = None) -> List[List[Dict]]:
    """
    دکمه‌های فعال را بر اساس row و col می‌چیند.
    - row: شماره سطر (بالا/پایین)
    - col: ترتیب داخل سطر (چپ/راست) — عدد کمتر = سمت راست در RTL تلگرام،
      ولی برای ثبات، بر اساس col صعودی مرتب می‌شود.
    اگر row/col نباشد، با per_row (پیش‌فرض ۳) خودکار چیده می‌شود.
    """
    if items is None:
        items = get_menu_buttons()
    active = [dict(x) for x in items if x.get("enabled", True)]
    if not active:
        return []

    # نرمال‌سازی col
    for i, x in enumerate(active):
        if x.get("col") is None:
            x["col"] = i
        try:
            x["col"] = int(x["col"])
        except Exception:
            x["col"] = i
        try:
            x["row"] = int(x["row"]) if x.get("row") is not None else None
        except Exception:
            x["row"] = None

    has_row = any(x.get("row") is not None for x in active)
    if has_row:
        for x in active:
            if x["row"] is None:
                x["row"] = 0
        groups: Dict[int, List[Dict]] = {}
        for x in active:
            groups.setdefault(x["row"], []).append(x)
        out = []
        for k in sorted(groups.keys()):
            out.append(sorted(groups[k], key=lambda z: z.get("col", 0)))
        return out

    pr = per_row if per_row is not None else get_buttons_per_row()
    # مرتب‌سازی کلی بر اساس col سپس برش به سطرها
    active_sorted = sorted(active, key=lambda z: z.get("col", 0))
    rows: List[List[Dict]] = []
    row: List[Dict] = []
    for x in active_sorted:
        row.append(x)
        if len(row) >= pr:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


# ---- ادمین‌های ربات (تلگرام) ----

def ensure_bot_admins_table():
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS bot_admins (
                id INT AUTO_INCREMENT PRIMARY KEY,
                telegram_id BIGINT NOT NULL UNIQUE,
                title VARCHAR(100) DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            conn.commit()
    finally:
        conn.close()


def list_bot_admins() -> list:
    ensure_bot_admins_table()
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM bot_admins ORDER BY id")
            return cur.fetchall() or []
    finally:
        conn.close()


def add_bot_admin(telegram_id: int, title: str = None) -> bool:
    ensure_bot_admins_table()
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT IGNORE INTO bot_admins (telegram_id, title) VALUES (%s,%s)",
                (int(telegram_id), title),
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception:
        return False
    finally:
        conn.close()


def remove_bot_admin(telegram_id: int) -> bool:
    ensure_bot_admins_table()
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM bot_admins WHERE telegram_id=%s", (int(telegram_id),))
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


def is_bot_admin_id(telegram_id: int) -> bool:
    """بررسی ادمین بودن (بدون در نظر گرفتن ADMIN_ID اصلی)."""
    try:
        ensure_bot_admins_table()
        conn = get_sync_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM bot_admins WHERE telegram_id=%s LIMIT 1", (int(telegram_id),))
                return cur.fetchone() is not None
        finally:
            conn.close()
    except Exception:
        return False
