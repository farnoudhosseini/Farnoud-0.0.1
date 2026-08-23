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
            cur.execute("""
            CREATE TABLE IF NOT EXISTS location_changes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                order_id INT NOT NULL,
                telegram_id BIGINT NOT NULL,
                from_group_id INT DEFAULT NULL,
                to_group_id INT DEFAULT NULL,
                to_group_name VARCHAR(200) DEFAULT NULL,
                price DECIMAL(18,0) NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_tg (telegram_id),
                INDEX idx_order (order_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS loyalty_accounts (
                telegram_id BIGINT PRIMARY KEY,
                points BIGINT NOT NULL DEFAULT 0,
                level VARCHAR(50) NOT NULL DEFAULT 'Bronze',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS loyalty_transactions (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                points INT NOT NULL,
                type VARCHAR(40) NOT NULL,
                reference_id VARCHAR(100) NULL,
                description VARCHAR(255) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uniq_loyalty_ref (telegram_id, type, reference_id),
                INDEX idx_loyalty_user (telegram_id, created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS reseller_requests (
                id INT AUTO_INCREMENT PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                description TEXT NOT NULL,
                status ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending',
                reseller_type ENUM('reseller','reseller_vip') DEFAULT NULL,
                admin_note TEXT,
                reviewed_at TIMESTAMP NULL DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_tg (telegram_id),
                INDEX idx_status (status)
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
                ("location_change_enabled", "1"),
                ("location_change_price", "0"),
                ("location_change_limit", "3"),
                ("btn_trial", "🎁 تست رایگان"),
                ("btn_reseller", "🤝 درخواست نمایندگی"),
                ("reseller_request_enabled", "1"),
                ("purchase_points_enabled", "1"),
                ("purchase_points_unit", "10000"),
                ("purchase_points_value", "1"),
            ]
            for k, v in defaults:
                cur.execute("INSERT IGNORE INTO settings (`key`, `value`) VALUES (%s,%s)", (k, v))
            for key, title, body in [
                ("btn_trial", "دکمه تست", "🎁 تست رایگان"),
                ("btn_reseller", "دکمه نمایندگی", "🤝 درخواست نمایندگی"),
                ("force_join_msg", "عضویت کانال", "برای استفاده از ربات ابتدا در کانال عضو شوید:\n[channel]\nسپس «بررسی عضویت» را بزنید."),
                ("force_phone_msg", "احراز موبایل", "برای ادامه، شماره موبایل خود را با دکمه زیر ارسال کنید."),
                ("reseller_request_prompt", "درخواست نمایندگی", "🤝 درخواست نمایندگی\n\nتوضیحات خود را بنویسید (مثلاً سابقه فروش، تعداد مشتری، شهر و ...):\nپس از ارسال، درخواست شما در صف بررسی ادمین قرار می‌گیرد."),
                ("reseller_request_sent", "ثبت درخواست نمایندگی", "✅ درخواست نمایندگی شما ثبت شد و در انتظار بررسی ادمین است.\nشماره درخواست: #[request_id]"),
                ("reseller_approved", "تایید نمایندگی", "🎉 درخواست نمایندگی شما تایید شد!\nنوع: [reseller_type]\nاز امکانات نماینده بهره‌مند شوید."),
                ("reseller_rejected", "رد نمایندگی", "❌ درخواست نمایندگی شما رد شد.\nدلیل: [reason]"),
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
    """پورسانت به معرف — با حداقل مبلغ، سقف ماهانه و نوتیف"""
    if get_setting_sync("referral_enabled", "1") != "1":
        return
    try:
        percent = float(get_setting_sync("referral_percent", "10") or 10)
        min_amt = int(get_setting_sync("referral_min_amount", "0") or 0)
        monthly_cap = int(get_setting_sync("referral_monthly_cap", "0") or 0)
    except Exception:
        percent, min_amt, monthly_cap = 10, 0, 0
    if percent <= 0 or amount <= 0:
        return
    if min_amt and amount < min_amt:
        return
    from db_users import get_bot_user, add_balance
    buyer = get_bot_user(buyer_id)
    if not buyer or not buyer.get("referrer_id"):
        return
    commission = int(amount * percent / 100)
    if commission <= 0:
        return
    # سقف ماهانه — بر اساس activity واقعی شارژ پورسانت.
    if monthly_cap > 0:
        conn = get_sync_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT COALESCE(SUM(CAST(SUBSTRING_INDEX(detail, '|', 1) AS DECIMAL)),0) AS s
                       FROM user_activity
                       WHERE telegram_id=%s AND action='balance_add'
                       AND detail LIKE '%%|ref_from_%%'
                       AND created_at >= DATE_FORMAT(NOW(), '%%Y-%%m-01')""",
                    (buyer["referrer_id"],),
                )
                used = int((cur.fetchone() or {}).get("s") or 0)
                if used >= monthly_cap:
                    return
                commission = min(commission, monthly_cap - used)
        except Exception:
            pass
        finally:
            conn.close()
    add_balance(buyer["referrer_id"], commission, f"ref_from_{buyer_id}")
    if get_setting_sync("referral_notify", "1") == "1":
        # ذخیره برای ارسال بعدی توسط ربات — در activity
        try:
            from db_users import log_activity
            log_activity(buyer["referrer_id"], "ref_notify", f"from={buyer_id}:amount={commission}")
        except Exception:
            pass


# ---- تغییر لوکیشن ----

def count_location_changes(telegram_id: int) -> int:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS c FROM location_changes WHERE telegram_id=%s",
                (telegram_id,),
            )
            row = cur.fetchone()
            return int((row or {}).get("c") or 0)
    finally:
        conn.close()


def record_location_change(order_id: int, telegram_id: int, from_gid=None,
                           to_gid=None, to_name=None, price: int = 0):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO location_changes
                   (order_id, telegram_id, from_group_id, to_group_id, to_group_name, price)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (order_id, telegram_id, from_gid, to_gid, to_name, price),
            )
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


# ---- درخواست نمایندگی ----

def create_reseller_request(telegram_id: int, description: str) -> int:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            # اگر درخواست pending دارد، اجازه دوباره نده
            cur.execute(
                "SELECT id FROM reseller_requests WHERE telegram_id=%s AND status='pending' LIMIT 1",
                (telegram_id,),
            )
            existing = cur.fetchone()
            if existing:
                return -int(existing["id"])  # منفی = قبلاً ثبت شده
            cur.execute(
                "INSERT INTO reseller_requests (telegram_id, description) VALUES (%s,%s)",
                (telegram_id, description.strip()[:2000]),
            )
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def get_reseller_request(rid: int) -> Optional[dict]:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM reseller_requests WHERE id=%s", (rid,))
            return cur.fetchone()
    finally:
        conn.close()


def list_reseller_requests(status: str = None, limit: int = 100) -> list:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            if status:
                cur.execute(
                    """SELECT r.*, u.username, u.first_name, u.last_name, u.role AS current_role
                       FROM reseller_requests r
                       LEFT JOIN bot_users u ON u.telegram_id = r.telegram_id
                       WHERE r.status=%s ORDER BY r.id DESC LIMIT %s""",
                    (status, limit),
                )
            else:
                cur.execute(
                    """SELECT r.*, u.username, u.first_name, u.last_name, u.role AS current_role
                       FROM reseller_requests r
                       LEFT JOIN bot_users u ON u.telegram_id = r.telegram_id
                       ORDER BY FIELD(r.status,'pending','approved','rejected'), r.id DESC
                       LIMIT %s""",
                    (limit,),
                )
            return cur.fetchall() or []
    finally:
        conn.close()


def review_reseller_request(rid: int, status: str, reseller_type: str = None,
                            admin_note: str = None) -> bool:
    """status: approved | rejected — فقط از وب‌پنل"""
    if status not in ("approved", "rejected"):
        return False
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM reseller_requests WHERE id=%s", (rid,))
            req = cur.fetchone()
            if not req or req["status"] != "pending":
                return False
            rtype = None
            if status == "approved":
                rtype = reseller_type if reseller_type in ("reseller", "reseller_vip") else "reseller"
            cur.execute(
                """UPDATE reseller_requests
                   SET status=%s, reseller_type=%s, admin_note=%s, reviewed_at=NOW()
                   WHERE id=%s""",
                (status, rtype, admin_note, rid),
            )
            if status == "approved" and rtype:
                cur.execute(
                    "UPDATE bot_users SET role=%s WHERE telegram_id=%s",
                    (rtype, req["telegram_id"]),
                )
            conn.commit()
            return True
    finally:
        conn.close()


def user_pending_reseller_request(telegram_id: int) -> Optional[dict]:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM reseller_requests WHERE telegram_id=%s AND status='pending' LIMIT 1",
                (telegram_id,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def calculate_purchase_points(amount: int) -> int:
    """محاسبه امتیاز خرید بر اساس تنظیمات وب‌پنل."""
    try:
        if get_setting_sync("purchase_points_enabled", "1") != "1":
            return 0
        unit = max(1, int(get_setting_sync("purchase_points_unit", "10000") or 10000))
        value = max(0, int(get_setting_sync("purchase_points_value", "1") or 1))
        amount = max(0, int(amount or 0))
        return (amount // unit) * value
    except Exception:
        return 0


def award_purchase_points(telegram_id: int, amount: int, order_id) -> int:
    """اعطای اتمیزه و idempotent امتیاز برای خرید موفق."""
    try:
        ensure_growth_tables()
    except Exception:
        pass
    points = calculate_purchase_points(amount)
    if points <= 0:
        return 0
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            ref = str(order_id)
            # ensure unique index exists (table may have been created without it)
            try:
                cur.execute(
                    """ALTER TABLE loyalty_transactions
                       ADD UNIQUE KEY uniq_loyalty_ref (telegram_id, type, reference_id)"""
                )
            except Exception:
                pass
            cur.execute(
                """SELECT id FROM loyalty_transactions
                   WHERE telegram_id=%s AND type='purchase' AND reference_id=%s
                   LIMIT 1""",
                (telegram_id, ref),
            )
            if cur.fetchone():
                return 0
            cur.execute(
                """INSERT INTO loyalty_transactions
                   (telegram_id, points, type, reference_id, description)
                   VALUES (%s,%s,'purchase',%s,%s)""",
                (telegram_id, points, ref, "امتیاز خرید"),
            )
            cur.execute(
                """INSERT INTO loyalty_accounts (telegram_id, points, level)
                   VALUES (%s,%s,'Bronze')
                   ON DUPLICATE KEY UPDATE points=points+VALUES(points)""",
                (telegram_id, points),
            )
            # refresh level name based on new total
            try:
                cur.execute("SELECT points FROM loyalty_accounts WHERE telegram_id=%s", (telegram_id,))
                row = cur.fetchone()
                total_pts = int((row or {}).get("points") or points)
                # reuse level logic without circular import
                levels = [
                    {"name": "Bronze", "min_points": 0},
                    {"name": "Silver", "min_points": 2500},
                    {"name": "Gold", "min_points": 7500},
                    {"name": "Diamond", "min_points": 15000},
                ]
                try:
                    raw = get_setting_sync("loyalty_config", "") or ""
                    if raw:
                        import json as _json
                        cfg = _json.loads(raw)
                        if isinstance(cfg.get("levels"), list) and cfg["levels"]:
                            levels = cfg["levels"]
                except Exception:
                    pass
                levels = sorted(levels, key=lambda x: int(x.get("min_points") or 0))
                level_name = "Bronze"
                for lv in levels:
                    if total_pts >= int(lv.get("min_points") or 0):
                        level_name = lv.get("name") or level_name
                cur.execute(
                    "UPDATE loyalty_accounts SET level=%s WHERE telegram_id=%s",
                    (level_name, telegram_id),
                )
            except Exception as e:
                print("award level update:", e)
            conn.commit()
            return points
    except Exception as e:
        print("award_purchase_points error:", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        conn.close()
