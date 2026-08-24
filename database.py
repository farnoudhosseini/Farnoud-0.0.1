# مدیریت اتصال به دیتابیس MySQL - پروژه فرنود

import re
import aiomysql
import pymysql
from config import DB_CONFIG, DB_CONFIG_SYNC

pool = None

# ==================== async (ربات) ====================

async def init_db():
    global pool
    pool = await aiomysql.create_pool(**DB_CONFIG)
    await ensure_tables_async()
    print("✅ اتصال به دیتابیس با موفقیت برقرار شد")

async def ensure_tables_async():
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    `key` VARCHAR(100) PRIMARY KEY,
                    `value` TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            await cur.execute("""
                INSERT IGNORE INTO settings (`key`, `value`)
                VALUES ('welcome_message', 'سلام! به ربات فرنود خوش آمدید 👋')
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS vpn_panels (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    slug VARCHAR(100) NOT NULL UNIQUE,
                    panel_type VARCHAR(30) NOT NULL DEFAULT 'pasarguard',
                    base_url VARCHAR(500) NOT NULL,
                    username VARCHAR(150) NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    last_status VARCHAR(50) DEFAULT NULL,
                    last_check_at TIMESTAMP NULL DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

async def close_db():
    global pool
    if pool:
        pool.close()
        await pool.wait_closed()
        print("🔌 اتصال دیتابیس بسته شد")

async def get_setting(key: str, default: str = "") -> str:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT `value` FROM settings WHERE `key` = %s LIMIT 1", (key,))
            row = await cur.fetchone()
            if row:
                return row[0] if row[0] is not None else default
            return default

async def set_setting(key: str, value: str):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO settings (`key`, `value`) VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE `value` = VALUES(`value`)
            """, (key, value))

# ==================== sync (پنل وب) ====================

def get_sync_connection():
    config = DB_CONFIG_SYNC.copy()
    config["cursorclass"] = pymysql.cursors.DictCursor
    return pymysql.connect(**config)

def _hash_password(password: str) -> str:
    from werkzeug.security import generate_password_hash
    return generate_password_hash(password)


def _verify_password(stored: str, password: str) -> bool:
    """پشتیبانی از هش werkzeug و پسوردهای قدیمی plaintext (مهاجرت نرم)."""
    if not stored or not password:
        return False
    if stored.startswith(("pbkdf2:", "scrypt:", "argon2:")):
        from werkzeug.security import check_password_hash
        return check_password_hash(stored, password)
    # سازگاری با نصب‌های قدیمی که پسورد plain داشتند
    return stored == password


def check_admin(username: str, password: str):
    connection = None
    try:
        connection = get_sync_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM admins WHERE username = %s LIMIT 1", (username,))
            admin = cursor.fetchone()
            if not admin:
                return None
            stored = admin.get("password") or ""
            if _verify_password(stored, password):
                # اگر پسورد هنوز plain بود، به هش ارتقا بده
                if not stored.startswith(("pbkdf2:", "scrypt:", "argon2:")):
                    try:
                        cursor.execute(
                            "UPDATE admins SET password=%s WHERE id=%s",
                            (_hash_password(password), admin["id"]),
                        )
                        connection.commit()
                    except Exception:
                        pass
                return admin
            return None
    except Exception as e:
        print(f"❌ خطا در بررسی ادمین: {e}")
        return None
    finally:
        if connection:
            connection.close()


def set_admin_password(password: str, admin_id: int = None) -> bool:
    """تنظیم/تغییر رمز ادمین با هش امن."""
    connection = None
    try:
        connection = get_sync_connection()
        with connection.cursor() as cursor:
            hashed = _hash_password(password)
            if admin_id:
                cursor.execute("UPDATE admins SET password=%s WHERE id=%s", (hashed, admin_id))
            else:
                cursor.execute(
                    "UPDATE admins SET password=%s WHERE id=(SELECT id FROM (SELECT id FROM admins ORDER BY id LIMIT 1) x)",
                    (hashed,),
                )
            connection.commit()
            return True
    except Exception as e:
        print(f"❌ خطا در تغییر رمز ادمین: {e}")
        return False
    finally:
        if connection:
            connection.close()

def get_setting_sync(key: str, default: str = "") -> str:
    connection = None
    try:
        connection = get_sync_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT `value` FROM settings WHERE `key` = %s LIMIT 1", (key,))
            row = cursor.fetchone()
            if row and row.get("value") is not None:
                return row["value"]
            return default
    except Exception as e:
        print(f"❌ خطا در خواندن تنظیم: {e}")
        return default
    finally:
        if connection:
            connection.close()

def set_setting_sync(key: str, value: str) -> bool:
    connection = None
    try:
        connection = get_sync_connection()
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO settings (`key`, `value`) VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE `value` = VALUES(`value`)
            """, (key, value))
            connection.commit()
            return True
    except Exception as e:
        print(f"❌ خطا در ذخیره تنظیم: {e}")
        return False
    finally:
        if connection:
            connection.close()

def ensure_tables_sync():
    connection = None
    try:
        connection = get_sync_connection()
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    `key` VARCHAR(100) PRIMARY KEY,
                    `value` TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            cursor.execute("""
                INSERT IGNORE INTO settings (`key`, `value`)
                VALUES ('welcome_message', 'سلام! به ربات فرنود خوش آمدید 👋')
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vpn_panels (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    slug VARCHAR(100) NOT NULL UNIQUE,
                    panel_type VARCHAR(30) NOT NULL DEFAULT 'pasarguard',
                    base_url VARCHAR(500) NOT NULL,
                    username VARCHAR(150) NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    last_status VARCHAR(50) DEFAULT NULL,
                    last_check_at TIMESTAMP NULL DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            connection.commit()
    except Exception as e:
        print(f"❌ خطا در ساخت جداول: {e}")
    finally:
        if connection:
            connection.close()

def slugify(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_-]+", "-", text)
    text = text.strip("-")
    return text[:80] or "panel"

def list_panels():
    connection = None
    try:
        connection = get_sync_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM vpn_panels ORDER BY id DESC")
            return cursor.fetchall() or []
    except Exception as e:
        print(f"❌ list_panels: {e}")
        return []
    finally:
        if connection:
            connection.close()

def get_panel_by_id(panel_id: int):
    connection = None
    try:
        connection = get_sync_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM vpn_panels WHERE id = %s LIMIT 1", (panel_id,))
            return cursor.fetchone()
    except Exception as e:
        print(f"❌ get_panel_by_id: {e}")
        return None
    finally:
        if connection:
            connection.close()

def get_panel_by_slug(slug: str):
    connection = None
    try:
        connection = get_sync_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM vpn_panels WHERE slug = %s LIMIT 1", (slug,))
            return cursor.fetchone()
    except Exception as e:
        print(f"❌ get_panel_by_slug: {e}")
        return None
    finally:
        if connection:
            connection.close()

def create_panel(name: str, panel_type: str, base_url: str, username: str, password: str, slug: str = None, api_key: str = None):
    """Returns (panel_id, slug) or (None, error_message)."""
    try:
        ensure_panel_max_sales()
    except Exception as e:
        print(f"ensure_panel_max_sales: {e}")
    connection = None
    try:
        connection = get_sync_connection()
        with connection.cursor() as cursor:
            final_slug = slug or slugify(name)
            base_slug = final_slug
            n = 1
            while True:
                cursor.execute("SELECT id FROM vpn_panels WHERE slug = %s LIMIT 1", (final_slug,))
                if not cursor.fetchone():
                    break
                n += 1
                final_slug = f"{base_slug}-{n}"

            # try with api_key column
            try:
                cursor.execute("""
                    INSERT INTO vpn_panels (name, slug, panel_type, base_url, username, password, api_key, is_active, last_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 1, 'connected')
                """, (name, final_slug, panel_type, base_url, username or "", password or "", api_key or None))
            except Exception as col_err:
                # fallback without api_key (old schema)
                print(f"create_panel api_key insert failed, fallback: {col_err}")
                cursor.execute("""
                    INSERT INTO vpn_panels (name, slug, panel_type, base_url, username, password, is_active, last_status)
                    VALUES (%s, %s, %s, %s, %s, %s, 1, 'connected')
                """, (name, final_slug, panel_type, base_url, username or "", password or ""))
            connection.commit()
            pid = cursor.lastrowid
            # if api_key exists and we fell back, try update
            if api_key and pid:
                try:
                    cursor.execute("UPDATE vpn_panels SET api_key=%s WHERE id=%s", (api_key, pid))
                    connection.commit()
                except Exception:
                    pass
            return pid, final_slug
    except Exception as e:
        print(f"❌ create_panel: {e}")
        return None, str(e)
    finally:
        if connection:
            connection.close()

def update_panel_status(panel_id: int, status: str):
    connection = None
    try:
        connection = get_sync_connection()
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE vpn_panels SET last_status = %s, last_check_at = NOW() WHERE id = %s
            """, (status, panel_id))
            connection.commit()
    except Exception as e:
        print(f"❌ update_panel_status: {e}")
    finally:
        if connection:
            connection.close()

def delete_panel(panel_id: int) -> bool:
    connection = None
    try:
        connection = get_sync_connection()
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM vpn_panels WHERE id = %s", (panel_id,))
            connection.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"❌ delete_panel: {e}")
        return False
    finally:
        if connection:
            connection.close()


def ensure_panel_max_sales():
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            for col, ddl in [
                ("max_sales", "INT DEFAULT NULL"),
                ("renew_mode", "VARCHAR(32) NOT NULL DEFAULT 'reset_both'"),
                ("api_key", "VARCHAR(512) DEFAULT NULL"),
                ("emoji", "VARCHAR(32) DEFAULT NULL"),
                ("premium_emoji", "VARCHAR(64) DEFAULT NULL"),
            ]:
                try:
                    cur.execute(f"ALTER TABLE vpn_panels ADD COLUMN {col} {ddl}")
                except Exception:
                    pass
            conn.commit()
    finally:
        conn.close()


def set_panel_field(panel_id: int, field: str, value) -> bool:
    allowed = {"max_sales", "renew_mode", "name", "is_active", "emoji", "premium_emoji"}
    if field not in allowed:
        return False
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE vpn_panels SET {field}=%s WHERE id=%s", (value, panel_id))
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        print(f"set_panel_field: {e}")
        return False
    finally:
        conn.close()

def set_panel_max_sales(panel_id: int, max_sales):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE vpn_panels SET max_sales=%s WHERE id=%s", (max_sales, panel_id))
            conn.commit()
    finally:
        conn.close()


def format_entity_label(entity: dict, for_miniapp: bool = False) -> str:
    """
    نام نمایشی پنل/دسته با ایموجی.
    for_miniapp=True → فقط ایموجی عادی (پریمیوم در مینی‌اپ نیست)
    for_miniapp=False → اولویت با ایموجی پریمیوم (کد p_ یا شناسه)
    """
    if not entity:
        return ""
    name = (entity.get("name") or "").strip()
    emoji = (entity.get("emoji") or "").strip()
    prem = (entity.get("premium_emoji") or "").strip()
    if for_miniapp:
        if emoji:
            return f"{emoji} {name}".strip()
        return name
    # ربات / دکمه اینلاین
    if prem:
        return f"{prem} {name}".strip()
    if emoji:
        return f"{emoji} {name}".strip()
    return name


def inline_button_from_entity(entity: dict, callback_data: str, max_len: int = 64):
    """ساخت InlineKeyboardButton با پشتیبانی ایموجی پریمیوم برای پنل/دسته."""
    from telegram import InlineKeyboardButton
    label = format_entity_label(entity, for_miniapp=False)
    text = label
    eid = None
    try:
        from db_extras import extract_premium_from_label
        text, eid = extract_premium_from_label(label)
    except Exception:
        # اگر premium_emoji عدد خالص باشد
        prem = (entity.get("premium_emoji") or "").strip()
        if prem.isdigit():
            eid = prem
            text = (entity.get("name") or "").strip() or "•"
        else:
            emoji = (entity.get("emoji") or "").strip()
            name = (entity.get("name") or "").strip()
            text = f"{emoji} {name}".strip() if emoji else name
    text = (text or "•")[:max_len]
    kwargs = {"text": text, "callback_data": callback_data}
    if eid:
        kwargs["icon_custom_emoji_id"] = str(eid)
    try:
        return InlineKeyboardButton(**kwargs)
    except TypeError:
        return InlineKeyboardButton(text, callback_data=callback_data)

