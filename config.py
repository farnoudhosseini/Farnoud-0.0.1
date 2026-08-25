# فایل تنظیمات کلی پروژه فرنود
# این فایل اطلاعات حساس را از فایل .env می‌خواند

import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME_TO_A_RANDOM_SECRET")
MINIAPP_URL = os.getenv("MINIAPP_URL", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")

# حالت اجرا: polling (پیش‌فرض / VPS) یا webhook (cPanel / aaPanel / هاست اشتراکی)
USE_WEBHOOK = os.getenv("USE_WEBHOOK", "0").strip().lower() in ("1", "true", "yes", "on")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/telegram/webhook").strip() or "/telegram/webhook"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()  # اختیاری؛ برای تأیید درخواست تلگرام
PUBLIC_BASE_URL = (os.getenv("PUBLIC_BASE_URL") or "").rstrip("/")

# Telegram Mini App
TELEGRAM_INIT_DATA_MAX_AGE = int(os.getenv("TELEGRAM_INIT_DATA_MAX_AGE", "86400"))
MIN_CHARGE = int(os.getenv("MIN_CHARGE", "10000"))
MAX_CHARGE = int(os.getenv("MAX_CHARGE", "50000000"))

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
