# کد تخفیف، تست رایگان، زیرمجموعه، احراز، لوکیشن

from database import get_sync_connection, get_setting_sync, set_setting_sync
from typing import Optional, Tuple
import secrets, string

def ensure_growth_tables():
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS discount_codes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                code VARCHAR(64) NOT NULL UNIQUE,
                percent DECIMAL(5,2) DEFAULT NULL,
                amount DECIMAL(18,0) DEFAULT NULL,
                max_uses INT NOT NULL DEFAULT 0,
                used_count INT NOT NULL DEFAULT 0,
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS trials (
                id INT AUTO_INCREMENT PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                panel_id INT NOT NULL,
                vpn_username VARCHAR(100) DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_trial_user (telegram_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            defaults = [
                ("force_join_enabled", "0"),
                ("force_join_channel", ""),
                ("force_phone_enabled", "0"),
                ("referral_percent", "10"),
                ("referral_enabled", "1"),
                ("trial_enabled", "0"),
                ("trial_panel_id", ""),
                ("trial_volume_gb", "1"),
                ("trial_days", "1"),
                ("trial_per_user", "1"),
                ("location_change_price", "0"),
                ("location_change_limit", "3"),
                ("btn_trial", "🎁 تست رایگان"),
            ]
            for k, v in defaults:
                cur.execute("INSERT IGNORE INTO settings (`key`, `value`) VALUES (%s,%s)", (k, v))
            for key, title, body in [
                ("btn_trial", "دکمه تست", "🎁 تست رایگان"),
                ("force_join_msg", "عضویت کانال", "برای استفاده از ربات ابتدا در کانال عضو شوید:\n[channel]\nسپس «بررسی عضویت» را بزنید."),
                ("force_phone_msg", "احراز موبایل", "برای ادامه، شماره موبایل خود را با دکمه زیر ارسال کنید."),
            ]:
                cur.execute(
                    "INSERT IGNORE INTO message_templates (`key`, title, body) VALUES (%s,%s,%s)",
                    (key, title, body),
                )
            conn.commit()
    finally:
        conn.close()

def list_discounts():
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM discount_codes ORDER BY id DESC")
            return cur.fetchall() or []
    finally:
        conn.close()

def create_discount(code, percent=None, amount=None, max_uses=0):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO discount_codes (code, percent, amount, max_uses) VALUES (%s,%s,%s,%s)",
                (code.upper().strip(), percent, amount, max_uses),
            )
            conn.commit()
            return True
    except Exception:
        return False
    finally:
        conn.close()

def apply_discount(code: str, price: int) -> Tuple[bool, int, str]:
    """returns ok, new_price, message"""
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM discount_codes WHERE code=%s AND is_active=1", (code.upper().strip(),))
            d = cur.fetchone()
            if not d:
                return False, price, "کد نامعتبر"
            if d["max_uses"] and d["used_count"] >= d["max_uses"]:
                return False, price, "ظرفیت کد تکمیل شده"
            new_price = price
            if d.get("percent"):
                new_price = int(price * (100 - float(d["percent"])) / 100)
            elif d.get("amount"):
                new_price = max(0, price - int(d["amount"]))
            cur.execute("UPDATE discount_codes SET used_count=used_count+1 WHERE id=%s", (d["id"],))
            conn.commit()
            return True, new_price, f"تخفیف اعمال شد — مبلغ جدید: {new_price:,}"
    finally:
        conn.close()

def has_used_trial(telegram_id: int) -> bool:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM trials WHERE telegram_id=%s", (telegram_id,))
            return cur.fetchone() is not None
    finally:
        conn.close()

def record_trial(telegram_id: int, panel_id: int, vpn_username: str):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO trials (telegram_id, panel_id, vpn_username) VALUES (%s,%s,%s)",
                (telegram_id, panel_id, vpn_username),
            )
            conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

def pay_referral_commission(buyer_id: int, amount: int):
    """پورسانت به معرف"""
    if get_setting_sync("referral_enabled", "1") != "1":
        return
    try:
        percent = float(get_setting_sync("referral_percent", "10") or 10)
    except Exception:
        percent = 10
    if percent <= 0 or amount <= 0:
        return
    from db_users import get_bot_user, add_balance
    buyer = get_bot_user(buyer_id)
    if not buyer or not buyer.get("referrer_id"):
        return
    commission = int(amount * percent / 100)
    if commission > 0:
        add_balance(buyer["referrer_id"], commission, f"ref_from_{buyer_id}")
