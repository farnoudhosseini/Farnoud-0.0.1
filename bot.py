# فایل اصلی ربات تلگرام
# در این نسخه هیچ دستوری تعریف نشده است

from telegram.ext import Application
from config import BOT_TOKEN
from database import init_db, close_db

async def post_init(application: Application):
    """
    این تابع بعد از راه‌اندازی ربات اجرا می‌شود
    اینجا فقط دیتابیس را متصل می‌کنیم
    """
    await init_db()

async def post_shutdown(application: Application):
    """
    این تابع هنگام خاموش شدن ربات اجرا می‌شود
    """
    await close_db()

def create_bot() -> Application:
    """
    ساخت شیء اصلی ربات
    در این نسخه هیچ Handler اضافه نشده است
    """
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    
    # در نسخه‌های بعدی هندلرها اینجا اضافه می‌شوند
    # مثلاً: application.add_handler(...)
    
    return application