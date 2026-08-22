# ایموجی پریمیوم، گزارش گروهی، تنظیمات منو

from __future__ import annotations
from typing import Optional
from database import get_sync_connection, get_setting_sync, set_setting_sync
import secrets
import string


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


def apply_premium_emojis(text: str) -> str:
    """
    جایگزینی کدهای p_... با تگ HTML ایموجی سفارشی تلگرام.
    خروجی باید با parse_mode=HTML ارسال شود.
    """
    if not text:
        return text
    emojis = list_premium_emojis()
    if not emojis:
        return text
    # طولانی‌ترها اول تا تداخل پیش نیاید
    for e in sorted(emojis, key=lambda x: len(x["code"]), reverse=True):
        code = e["code"]
        eid = e["custom_emoji_id"]
        # تلگرام: <tg-emoji emoji-id="ID">😀</tg-emoji>
        replacement = f'<tg-emoji emoji-id="{eid}">✨</tg-emoji>'
        text = text.replace(code, replacement)
    return text


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
