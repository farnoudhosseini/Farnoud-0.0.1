# فایل تنظیمات کلی پروژه فرنود
# این فایل اطلاعات حساس را از فایل .env می‌خواند

import os
from dotenv import load_dotenv

# بارگذاری متغیرهای محیطی از فایل .env
load_dotenv()

# توکن ربات تلگرام
BOT_TOKEN = os.getenv("BOT_TOKEN")

# آیدی عددی ادمین اصلی (تلگرام)
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# کلید امنیتی Flask برای سشن پنل مدیریت
SECRET_KEY = os.getenv("SECRET_KEY", "farnoud_8xK9mP2qR7vL4nW6jH3tY5bC1aZ0eD9")

# تنظیمات دیتابیس MySQL (XAMPP) - برای ربات (aiomysql)
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "db": os.getenv("DB_NAME", "farnoudbot"),
    "charset": "utf8mb4",
    "autocommit": True
}

# تنظیمات دیتابیس برای پنل مدیریت (pymysql)
DB_CONFIG_SYNC = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "farnoudbot"),
    "charset": "utf8mb4",
}
