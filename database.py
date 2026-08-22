# مدیریت اتصال به دیتابیس MySQL
# این فایل فقط اتصال را برقرار می‌کند و هیچ جدولی نمی‌سازد

import aiomysql
from config import DB_CONFIG

# متغیر سراسری برای نگهداری استخر اتصال
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