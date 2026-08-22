# مدیریت اتصال به دیتابیس MySQL - پروژه فرنود
# بخش async برای ربات تلگرام
# بخش sync برای پنل مدیریت وب

import aiomysql
import pymysql
from config import DB_CONFIG, DB_CONFIG_SYNC

# ==================== بخش ربات (async) ====================

pool = None

async def init_db():
    """
    ایجاد استخر اتصال به دیتابیس
    این تابع فقط یک بار در شروع ربات صدا زده می‌شود
    """
    global pool
    pool = await aiomysql.create_pool(**DB_CONFIG)
    print("✅ اتصال به دیتابیس با موفقیت برقرار شد")

async def close_db():
    """
    بستن استخر اتصال هنگام خاموش شدن ربات
    """
    global pool
    if pool:
        pool.close()
        await pool.wait_closed()
        print("🔌 اتصال دیتابیس بسته شد")

async def get_connection():
    """
    گرفتن یک اتصال از استخر برای استفاده در کوئری‌ها
    """
    if pool is None:
        raise Exception("استخر دیتابیس هنوز مقداردهی نشده است")
    return await pool.acquire()

# ==================== بخش پنل مدیریت (sync) ====================

def get_sync_connection():
    """
    ایجاد اتصال همگام به دیتابیس برای پنل مدیریت
    """
    config = DB_CONFIG_SYNC.copy()
    config["cursorclass"] = pymysql.cursors.DictCursor
    return pymysql.connect(**config)

def check_admin(username: str, password: str):
    """
    بررسی وجود ادمین در جدول admins
    این تابع فقط برای لاگین پنل مدیریت استفاده می‌شود
    """
    connection = None
    try:
        connection = get_sync_connection()
        with connection.cursor() as cursor:
            sql = "SELECT * FROM admins WHERE username = %s LIMIT 1"
            cursor.execute(sql, (username,))
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
