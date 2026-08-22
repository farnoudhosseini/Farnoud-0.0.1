# فایل اصلی ربات تلگرام فرنود

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)
from config import BOT_TOKEN, ADMIN_ID
from database import init_db, close_db
from handlers.start import start_command
from handlers.admin import (
    admin_panel,
    admin_callback,
    receive_welcome_message,
    WAITING_WELCOME,
)

async def post_init(application: Application):
    """بعد از راه‌اندازی ربات"""
    await init_db()

async def post_shutdown(application: Application):
    """هنگام خاموش شدن ربات"""
    await close_db()

def create_bot() -> Application:
    """ساخت شیء اصلی ربات و ثبت هندلرها"""
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # دستور /start
    application.add_handler(CommandHandler("start", start_command))

    # مکالمه تنظیم پیام خوش‌آمدگویی (ادمین)
    welcome_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_callback, pattern="^set_welcome$"),
        ],
        states={
            WAITING_WELCOME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_welcome_message),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(admin_callback, pattern="^admin_back$"),
            CommandHandler("start", start_command),
        ],
        allow_reentry=True,
    )
    application.add_handler(welcome_conv)

    # سایر دکمه‌های پنل ادمین داخل ربات
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))

    # دستور /admin برای باز کردن پنل مدیریت داخل ربات
    application.add_handler(CommandHandler("admin", admin_panel))

    return application
