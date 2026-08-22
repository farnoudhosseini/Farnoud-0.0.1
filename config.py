# فایل تنظیمات کلی ربات
# این فایل اطلاعات حساس را از فایل .env می‌خواند

import os
from dotenv import load_dotenv

# بارگذاری متغیرهای محیطی از فایل .env
load_dotenv()

# توکن ربات تلگرام
BOT_TOKEN = os.getenv("BOT_TOKEN")

# آیدی عددی ادمین اصلی
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# تنظیمات دیتابیس MySQL (XAMPP)
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "db": os.getenv("DB_NAME", "vpn_bot"),
    "charset": "utf8mb4",
    "autocommit": True
}