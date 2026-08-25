# عملیات دیتابیس: کاربران ربات، کیف پول، پرداخت، کد هدیه

from __future__ import annotations

import secrets
import string
from typing import Any, Optional

from database import get_sync_connection, ensure_tables_sync

ROLE_LABELS = {
    "user": "کاربر عادی",
    "reseller": "نماینده عادی",
    "reseller_vip": "نماینده ویژه",
    "vip": "وی‌آی‌پی",
}

def ensure_user_tables():
    ensure_tables_sync()
    connection = None
    try:
        connection = get_sync_connection()
        with connection.cursor() as cur:
            with open("/opt/Farnoud-0.0.1/models_schema.sql", "r") as f:
                pass
    except Exception:
        pass
    # inline ensure
    connection = get_sync_connection()
    try:
        with connection.cursor() as cur:
            for stmt in _SCHEMA_STATEMENTS:
                try:
                    cur.execute(stmt)
                except Exception as e:
                    if "Duplicate" not in str(e):
                        print(f"schema warn: {e}")
            # Safe migrations for existing production payment data.
            for ddl in (
                "ALTER TABLE charge_requests ADD COLUMN variza_slug VARCHAR(120) NULL",
                "ALTER TABLE charge_requests ADD COLUMN variza_amount DECIMAL(18,0) NULL",
                "ALTER TABLE charge_requests ADD COLUMN variza_attempt_code VARCHAR(120) NULL",
                "ALTER TABLE charge_requests ADD COLUMN variza_delivery_id VARCHAR(120) NULL",
                "ALTER TABLE charge_requests ADD COLUMN paid_at TIMESTAMP NULL",
            ):
                try: cur.execute(ddl)
                except Exception: pass
            for key, value in (
                ("variza_enabled", "0"), ("variza_api_key", ""), ("variza_webhook_secret", ""),
                ("variza_title", "پرداخت واریزا"), ("public_base_url", ""),
                ("payment_method_card_enabled", "1"), ("card_payment_title", "کارت به کارت"),
                ("card_min_purchases", "0"),  # 0=همیشه، 1=از خرید دوم به بعد
                ("stars_enabled", "0"), ("stars_title", "⭐ پرداخت با استارز"),
                ("stars_rate", "1000"),  # تومان به‌ازای هر استار
                ("stars_payment_title", "⭐ استارز تلگرام"),
                ("trial_reset_message", "🎁 تست رایگان شما دوباره فعال شد!\nاکنون می‌توانید مجدداً از تست رایگان استفاده کنید."),
            ):
                try: cur.execute("INSERT IGNORE INTO settings (`key`,`value`) VALUES (%s,%s)", (key, value))
                except Exception: pass
            try: cur.execute("INSERT IGNORE INTO payment_methods (method_key,title,is_active) VALUES ('variza','پرداخت واریزا',0)")
            except Exception: pass
            try: cur.execute("CREATE UNIQUE INDEX uniq_charge_variza_slug ON charge_requests (variza_slug)")
            except Exception: pass
            connection.commit()
    finally:
        connection.close()

_SCHEMA_STATEMENTS = [
"""CREATE TABLE IF NOT EXISTS bot_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    telegram_id BIGINT NOT NULL UNIQUE,
    username VARCHAR(100) DEFAULT NULL,
    first_name VARCHAR(150) DEFAULT NULL,
    last_name VARCHAR(150) DEFAULT NULL,
    phone VARCHAR(30) DEFAULT NULL,
    balance DECIMAL(18,0) NOT NULL DEFAULT 0,
    role ENUM('user','reseller','reseller_vip','vip') NOT NULL DEFAULT 'user',
    referrer_id BIGINT DEFAULT NULL,
    invite_code VARCHAR(32) NOT NULL,
    is_blocked TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP NULL DEFAULT NULL,
    INDEX idx_referrer (referrer_id),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
"""CREATE TABLE IF NOT EXISTS user_activity (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    action VARCHAR(80) NOT NULL,
    detail TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_uid (telegram_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
"""CREATE TABLE IF NOT EXISTS message_templates (
    `key` VARCHAR(80) PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    body TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
"""CREATE TABLE IF NOT EXISTS payment_cards (
    id INT AUTO_INCREMENT PRIMARY KEY,
    card_number VARCHAR(32) NOT NULL,
    owner_name VARCHAR(150) NOT NULL,
    bank_name VARCHAR(100) DEFAULT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
"""CREATE TABLE IF NOT EXISTS payment_methods (
    id INT AUTO_INCREMENT PRIMARY KEY,
    method_key VARCHAR(40) NOT NULL UNIQUE,
    title VARCHAR(100) NOT NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    config_json TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
"""CREATE TABLE IF NOT EXISTS charge_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    amount DECIMAL(18,0) NOT NULL,
    method_key VARCHAR(40) NOT NULL DEFAULT 'card',
    card_id INT DEFAULT NULL,
    status ENUM('pending_payment','waiting_receipt','pending_review','approved','rejected','cancelled') NOT NULL DEFAULT 'pending_payment',
    receipt_file_id VARCHAR(255) DEFAULT NULL,
    admin_note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_tg (telegram_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
"""CREATE TABLE IF NOT EXISTS gift_codes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(64) NOT NULL UNIQUE,
    amount DECIMAL(18,0) NOT NULL,
    max_uses INT NOT NULL DEFAULT 1,
    used_count INT NOT NULL DEFAULT 0,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    expires_at TIMESTAMP NULL DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
"""CREATE TABLE IF NOT EXISTS gift_code_uses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code_id INT NOT NULL,
    telegram_id BIGINT NOT NULL,
    amount DECIMAL(18,0) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_code_user (code_id, telegram_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
"""INSERT IGNORE INTO payment_methods (method_key, title, is_active) VALUES ('card', 'کارت به کارت', 1)""",
"""INSERT IGNORE INTO settings (`key`, `value`) VALUES ('min_charge', '10000'), ('max_charge', '50000000')""",
"""INSERT IGNORE INTO message_templates (`key`, title, body) VALUES
('wallet_main', 'کیف پول من', '💰 کیف پول شما\\n\\n👤 کاربر: [name]\\n🆔 آیدی: [id]\\n💳 موجودی: [balance] تومان\\n🎭 نقش: [role]\\n🔗 لینک دعوت: [invite_link]\\n👥 زیرمجموعه‌ها: [referrals]'),
('wallet_charge', 'شارژ حساب', 'مبلغ شارژ را وارد کنید.\\nحداقل: [min_charge] تومان\\nحداکثر: [max_charge] تومان'),
('wallet_gift', 'کد هدیه', '🎁 کد هدیه خود را ارسال کنید:'),
('wallet_referrals', 'زیرمجموعه', '👥 تعداد زیرمجموعه: [referrals]\\n🔗 لینک دعوت شما:\\n[invite_link]'),
('charge_invoice', 'فاکتور شارژ', '🧾 فاکتور شارژ\\n\\nمبلغ: [amount] تومان\\nشناسه: [invoice_id]\\n\\nروش پرداخت را انتخاب کنید.'),
('charge_card_info', 'کارت به کارت', '💳 لطفاً مبلغ [amount] تومان را به کارت زیر واریز کنید:\\n\\nشماره کارت: [card_number]\\nبه نام: [card_owner]\\n\\nپس از واریز، تصویر رسید را ارسال کنید.'),
('charge_waiting', 'در انتظار تایید', '⏳ رسید شما ثبت شد و در انتظار تایید ادمین است.\\nشناسه درخواست: [invoice_id]'),
('charge_approved', 'تایید شارژ', '✅ شارژ حساب شما به مبلغ [amount] تومان تایید شد.\\nموجودی جدید: [balance] تومان'),
('charge_rejected', 'رد شارژ', '❌ درخواست شارژ شما رد شد.\\nدلیل: [reason]')""",
]

def _gen_invite() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))

def upsert_bot_user(tg_user, referrer_id: int = None) -> dict:
    """ثبت یا به‌روزرسانی کاربر ربات هنگام /start"""
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM bot_users WHERE telegram_id = %s", (tg_user.id,))
            row = cur.fetchone()
            if row:
                cur.execute(
                    """UPDATE bot_users SET username=%s, first_name=%s, last_name=%s, last_seen_at=NOW()
                       WHERE telegram_id=%s""",
                    (tg_user.username, tg_user.first_name, tg_user.last_name, tg_user.id),
                )
                conn.commit()
                cur.execute("SELECT * FROM bot_users WHERE telegram_id = %s", (tg_user.id,))
                return cur.fetchone()
            invite = _gen_invite()
            # جلوگیری از خودمعرفی
            ref = referrer_id if referrer_id and referrer_id != tg_user.id else None
            cur.execute(
                """INSERT INTO bot_users
                   (telegram_id, username, first_name, last_name, invite_code, referrer_id, last_seen_at)
                   VALUES (%s,%s,%s,%s,%s,%s,NOW())""",
                (tg_user.id, tg_user.username, tg_user.first_name, tg_user.last_name, invite, ref),
            )
            conn.commit()
            log_activity(tg_user.id, "register", f"referrer={ref}")
            cur.execute("SELECT * FROM bot_users WHERE telegram_id = %s", (tg_user.id,))
            created = cur.fetchone()
            # signup bonus is granted once, only when a real referrer exists.
            if ref:
                try:
                    from database import get_setting_sync
                    bonus = int(get_setting_sync("referral_signup_bonus", "0") or 0)
                    if bonus > 0:
                        add_balance(ref, bonus, f"ref_signup_{tg_user.id}")
                except Exception:
                    pass
            return created
    finally:
        conn.close()

def get_bot_user(telegram_id: int) -> Optional[dict]:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM bot_users WHERE telegram_id = %s", (telegram_id,))
            return cur.fetchone()
    finally:
        conn.close()

def get_bot_user_by_invite(code: str) -> Optional[dict]:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM bot_users WHERE invite_code = %s", (code,))
            return cur.fetchone()
    finally:
        conn.close()

def list_bot_users(offset=0, limit=50, search=None) -> tuple:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            if search:
                like = f"%{search}%"
                cur.execute(
                    """SELECT * FROM bot_users WHERE username LIKE %s OR first_name LIKE %s
                       OR CAST(telegram_id AS CHAR) LIKE %s OR phone LIKE %s
                       ORDER BY id DESC LIMIT %s OFFSET %s""",
                    (like, like, like, like, limit, offset),
                )
                rows = cur.fetchall() or []
                cur.execute(
                    """SELECT COUNT(*) AS c FROM bot_users WHERE username LIKE %s OR first_name LIKE %s
                       OR CAST(telegram_id AS CHAR) LIKE %s OR phone LIKE %s""",
                    (like, like, like, like),
                )
            else:
                cur.execute("SELECT * FROM bot_users ORDER BY id DESC LIMIT %s OFFSET %s", (limit, offset))
                rows = cur.fetchall() or []
                cur.execute("SELECT COUNT(*) AS c FROM bot_users")
            total = (cur.fetchone() or {}).get("c", 0)
            return rows, total
    finally:
        conn.close()

def update_bot_user(telegram_id: int, **fields) -> bool:
    allowed = {"username", "first_name", "last_name", "phone", "balance", "role", "is_blocked"}
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"`{k}`=%s")
            vals.append(v)
    if not sets:
        return False
    vals.append(telegram_id)
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE bot_users SET {', '.join(sets)} WHERE telegram_id=%s", vals)
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()

def _ensure_wallet_tx_table(cur):
    try:
        cur.execute("""CREATE TABLE IF NOT EXISTS wallet_transactions (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            type VARCHAR(32) NOT NULL DEFAULT 'adjust',
            amount BIGINT NOT NULL DEFAULT 0,
            balance_after BIGINT NOT NULL DEFAULT 0,
            reference_type VARCHAR(64) NULL,
            reference_id VARCHAR(64) NULL,
            description VARCHAR(255) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_wt_user (telegram_id),
            INDEX idx_wt_created (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    except Exception:
        pass


def add_balance(telegram_id: int, amount: int, reason: str = "") -> Optional[dict]:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE bot_users SET balance = balance + %s WHERE telegram_id = %s",
                (amount, telegram_id),
            )
            cur.execute("SELECT balance FROM bot_users WHERE telegram_id = %s", (telegram_id,))
            row = cur.fetchone() or {}
            new_bal = int(row.get("balance") or 0)
            # mirror into wallet_transactions for miniapp history
            try:
                _ensure_wallet_tx_table(cur)
                tx_type = "topup" if amount > 0 else "purchase"
                if reason and ("refund" in str(reason) or "reimburse" in str(reason)):
                    tx_type = "refund"
                elif reason and str(reason).startswith("charge"):
                    tx_type = "topup"
                elif reason and ("order" in str(reason) or "renew" in str(reason) or "hourly" in str(reason)):
                    tx_type = "purchase"
                cur.execute(
                    """INSERT INTO wallet_transactions
                       (telegram_id, type, amount, balance_after, reference_type, reference_id, description)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        telegram_id,
                        tx_type,
                        int(amount),
                        new_bal,
                        "balance",
                        (str(reason) or "")[:80],
                        (str(reason) or "تراکنش کیف پول")[:255],
                    ),
                )
            except Exception as e:
                # table may not exist yet on very old DBs
                print("wallet_transactions insert:", e)
            conn.commit()
            log_activity(telegram_id, "balance_add", f"{amount}|{reason}")
            cur.execute("SELECT * FROM bot_users WHERE telegram_id = %s", (telegram_id,))
            return cur.fetchone()
    finally:
        conn.close()

def count_referrals(telegram_id: int) -> int:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM bot_users WHERE referrer_id = %s", (telegram_id,))
            return int((cur.fetchone() or {}).get("c") or 0)
    finally:
        conn.close()

def log_activity(telegram_id: int, action: str, detail: str = None):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_activity (telegram_id, action, detail) VALUES (%s,%s,%s)",
                (telegram_id, action, detail),
            )
            conn.commit()
    except Exception as e:
        print(f"activity log: {e}")
    finally:
        conn.close()

def get_user_activity(telegram_id: int, limit=30) -> list:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM user_activity WHERE telegram_id=%s ORDER BY id DESC LIMIT %s",
                (telegram_id, limit),
            )
            return cur.fetchall() or []
    finally:
        conn.close()

def get_template(key: str) -> str:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT body FROM message_templates WHERE `key`=%s", (key,))
            row = cur.fetchone()
            return row["body"] if row else ""
    finally:
        conn.close()

def list_templates() -> list:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM message_templates ORDER BY `key`")
            return cur.fetchall() or []
    finally:
        conn.close()

def set_template(key: str, body: str, title: str = None) -> bool:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            if title:
                cur.execute(
                    """INSERT INTO message_templates (`key`, title, body) VALUES (%s,%s,%s)
                       ON DUPLICATE KEY UPDATE body=VALUES(body), title=VALUES(title)""",
                    (key, title, body),
                )
            else:
                cur.execute(
                    """INSERT INTO message_templates (`key`, title, body) VALUES (%s,%s,%s)
                       ON DUPLICATE KEY UPDATE body=VALUES(body)""",
                    (key, key, body),
                )
            conn.commit()
            return True
    finally:
        conn.close()

def render_template(key: str, variables: dict) -> str:
    text = get_template(key) or ""
    for k, v in variables.items():
        text = text.replace(f"[{k}]", str(v if v is not None else ""))
    # جایگزینی ایموجی پریمیوم p_...
    try:
        from db_extras import apply_premium_emojis
        text = apply_premium_emojis(text)
    except Exception:
        pass
    return text

def user_vars(user: dict, bot_username: str = "") -> dict:
    refs = count_referrals(user["telegram_id"])
    invite = user.get("invite_code") or ""
    link = f"https://t.me/{bot_username}?start={invite}" if bot_username else invite
    name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")])) or user.get("username") or str(user["telegram_id"])
    from database import get_setting_sync
    return {
        "id": user["telegram_id"],
        "username": user.get("username") or "—",
        "name": name,
        "balance": f"{int(user.get('balance') or 0):,}",
        "role": ROLE_LABELS.get(user.get("role"), user.get("role")),
        "phone": user.get("phone") or "—",
        "invite_link": link,
        "invite_code": invite,
        "referrals": refs,
        "refrals": refs,  # alias رایج
        "min_charge": get_setting_sync("min_charge", "10000"),
        "max_charge": get_setting_sync("max_charge", "50000000"),
    }

# ---- cards & charges ----
def list_cards(active_only=False) -> list:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            if active_only:
                cur.execute("SELECT * FROM payment_cards WHERE is_active=1 ORDER BY sort_order, id")
            else:
                cur.execute("SELECT * FROM payment_cards ORDER BY sort_order, id")
            return cur.fetchall() or []
    finally:
        conn.close()

def add_card(number: str, owner: str, bank: str = None) -> int:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO payment_cards (card_number, owner_name, bank_name) VALUES (%s,%s,%s)",
                (number, owner, bank),
            )
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()

def delete_card(card_id: int) -> bool:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM payment_cards WHERE id=%s", (card_id,))
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()

def toggle_card(card_id: int, active: bool) -> bool:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE payment_cards SET is_active=%s WHERE id=%s", (1 if active else 0, card_id))
            conn.commit()
            return True
    finally:
        conn.close()

def set_payment_method_state(method_key: str, active: bool) -> bool:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE payment_methods SET is_active=%s WHERE method_key=%s", (1 if active else 0, method_key))
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()

def set_payment_method_title(method_key: str, title: str) -> bool:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE payment_methods SET title=%s WHERE method_key=%s", (title[:100], method_key))
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()

def list_payment_methods(active_only=True) -> list:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            if active_only:
                cur.execute("SELECT * FROM payment_methods WHERE is_active=1")
            else:
                cur.execute("SELECT * FROM payment_methods")
            return cur.fetchall() or []
    finally:
        conn.close()

def create_charge(telegram_id: int, amount: int, method_key="card", card_id=None) -> int:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO charge_requests (telegram_id, amount, method_key, card_id, status)
                   VALUES (%s,%s,%s,%s,'pending_payment')""",
                (telegram_id, amount, method_key, card_id),
            )
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()

def get_charge(charge_id: int) -> Optional[dict]:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM charge_requests WHERE id=%s", (charge_id,))
            return cur.fetchone()
    finally:
        conn.close()

def set_charge_receipt(charge_id: int, file_id: str):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE charge_requests SET receipt_file_id=%s, status='pending_review' WHERE id=%s",
                (file_id, charge_id),
            )
            conn.commit()
    finally:
        conn.close()

def list_pending_charges() -> list:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM charge_requests WHERE status='pending_review' ORDER BY id ASC"
            )
            return cur.fetchall() or []
    finally:
        conn.close()

def approve_charge(charge_id: int) -> Optional[dict]:
    ch = get_charge(charge_id)
    if not ch or ch["status"] != "pending_review":
        return None
    user = add_balance(ch["telegram_id"], int(ch["amount"]), f"charge#{charge_id}")
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE charge_requests SET status='approved' WHERE id=%s", (charge_id,))
            conn.commit()
    finally:
        conn.close()
    return user

def reject_charge(charge_id: int, reason: str = "") -> bool:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE charge_requests SET status='rejected', admin_note=%s WHERE id=%s AND status='pending_review'",
                (reason, charge_id),
            )
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()

def redeem_gift(telegram_id: int, code: str) -> tuple:
    """returns (ok, message, amount)"""
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM gift_codes WHERE code=%s", (code.strip().upper(),))
            g = cur.fetchone()
            if not g or not g["is_active"]:
                return False, "کد نامعتبر است", 0
            if g["used_count"] >= g["max_uses"]:
                return False, "ظرفیت استفاده از این کد تکمیل شده", 0
            cur.execute(
                "SELECT id FROM gift_code_uses WHERE code_id=%s AND telegram_id=%s",
                (g["id"], telegram_id),
            )
            if cur.fetchone():
                return False, "قبلاً از این کد استفاده کرده‌اید", 0
            cur.execute(
                "INSERT INTO gift_code_uses (code_id, telegram_id, amount) VALUES (%s,%s,%s)",
                (g["id"], telegram_id, g["amount"]),
            )
            cur.execute("UPDATE gift_codes SET used_count = used_count + 1 WHERE id=%s", (g["id"],))
            conn.commit()
        add_balance(telegram_id, int(g["amount"]), f"gift:{code}")
        return True, "کد با موفقیت اعمال شد", int(g["amount"])
    except Exception as e:
        return False, f"خطا: {e}", 0
    finally:
        conn.close()

def list_gift_codes() -> list:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM gift_codes ORDER BY id DESC")
            return cur.fetchall() or []
    finally:
        conn.close()

def create_gift_code(code: str, amount: int, max_uses: int = 1) -> bool:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO gift_codes (code, amount, max_uses) VALUES (%s,%s,%s)",
                (code.strip().upper(), amount, max_uses),
            )
            conn.commit()
            return True
    except Exception:
        return False
    finally:
        conn.close()


def count_user_paid_orders(telegram_id: int) -> int:
    """تعداد خریدهای موفق کاربر (برای محدودیت نمایش کارت)."""
    from database import get_sync_connection
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) AS c FROM service_orders
                   WHERE telegram_id=%s AND status IN ('paid','provisioned','expired')
                     AND COALESCE(amount,0) > 0""",
                (int(telegram_id),),
            )
            row = cur.fetchone() or {}
            return int(row.get("c") or 0)
    except Exception as e:
        print("count_user_paid_orders:", e)
        return 0
    finally:
        conn.close()


def user_can_see_card(telegram_id: int) -> bool:
    """آیا کاربر مجاز به دیدن شماره کارت هست؟"""
    from database import get_setting_sync
    try:
        min_p = int(get_setting_sync("card_min_purchases", "0") or 0)
    except Exception:
        min_p = 0
    if min_p <= 0:
        return True
    return count_user_paid_orders(telegram_id) >= min_p


def ensure_stars_payment_method():
    """ثبت روش پرداخت استارز در جدول payment_methods."""
    from database import get_sync_connection
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT IGNORE INTO payment_methods (method_key, title, is_active) VALUES ('stars', %s, 0)",
                ("⭐ استارز تلگرام",),
            )
            conn.commit()
    except Exception as e:
        print("ensure_stars_payment_method:", e)
    finally:
        conn.close()

