# فایل تنظیمات کلی پروژه فرنود
# این فایل اطلاعات حساس را از فایل .env می‌خواند

import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME_TO_A_RANDOM_SECRET")

# تنظیمات دیتابیس برای ربات (aiomysql)
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
