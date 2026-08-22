# مدیریت اتصال به دیتابیس MySQL - پروژه فرنود
# بخش async برای ربات تلگرام
# بخش sync برای پنل مدیریت وب

import aiomysql
import pymysql
from config import DB_CONFIG, DB_CONFIG_SYNC

# ==================== بخش ربات (async) ====================

pool = None

async def init_db():
    """ایجاد استخر اتصال و اطمینان از وجود جداول لازم"""
    global pool
    pool = await aiomysql.create_pool(**DB_CONFIG)
    await ensure_tables_async()
    print("✅ اتصال به دیتابیس با موفقیت برقرار شد")

async def ensure_tables_async():
    """ساخت جداول مورد نیاز اگر وجود نداشته باشند"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    `key` VARCHAR(100) PRIMARY KEY,
                    `value` TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            # پیام خوش‌آمدگویی پیش‌فرض
            await cur.execute("""
                INSERT IGNORE INTO settings (`key`, `value`)
                VALUES ('welcome_message', 'سلام! به ربات فرنود خوش آمدید 👋')
            """)

async def close_db():
    global pool
    if pool:
        pool.close()
        await pool.wait_closed()
        print("🔌 اتصال دیتابیس بسته شد")

async def get_setting(key: str, default: str = "") -> str:
    """خواندن یک تنظیم از دیتابیس (async)"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT `value` FROM settings WHERE `key` = %s LIMIT 1", (key,))
            row = await cur.fetchone()
            if row:
                return row[0] if row[0] is not None else default
            return default

async def set_setting(key: str, value: str):
    """ذخیره یک تنظیم در دیتابیس (async)"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO settings (`key`, `value`) VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE `value` = VALUES(`value`)
            """, (key, value))

# ==================== بخش پنل مدیریت (sync) ====================

def get_sync_connection():
    config = DB_CONFIG_SYNC.copy()
    config["cursorclass"] = pymysql.cursors.DictCursor
    return pymysql.connect(**config)

def check_admin(username: str, password: str):
    """بررسی وجود ادمین در جدول admins"""
    connection = None
    try:
        connection = get_sync_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM admins WHERE username = %s LIMIT 1", (username,))
            admin = cursor.fetchone()
            if admin and admin.get("password") == password:
                return admin
            return None
    except Exception as e:
        print(f"❌ خطا در بررسی ادمین: {e}")
        return None
    finally:
        if connection:
            connection.close()

def get_setting_sync(key: str, default: str = "") -> str:
    """خواندن تنظیم (sync)"""
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
    """ذخیره تنظیم (sync)"""
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
    """ساخت جداول از سمت پنل در صورت نیاز"""
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
            connection.commit()
    except Exception as e:
        print(f"❌ خطا در ساخت جداول: {e}")
    finally:
        if connection:
            connection.close()
