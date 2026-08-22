# فایل اصلی ربات تلگرام فرنود

from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters,
)
from config import BOT_TOKEN
from database import init_db, close_db
from handlers.start import start_command
from handlers.admin import (
    admin_panel, admin_callback, receive_welcome_message,
    receive_user_field, WAITING_WELCOME, WAITING_USER_FIELD,
)

async def post_init(application: Application):
    await init_db()

async def post_shutdown(application: Application):
    await close_db()

def create_bot() -> Application:
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    application.add_handler(CommandHandler("start", start_command))

    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_callback, pattern="^(set_welcome|admin_padduser_|admin_pedit_)"),
        ],
        states={
            WAITING_WELCOME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_welcome_message)],
            WAITING_USER_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_user_field)],
        },
        fallbacks=[
            CallbackQueryHandler(admin_callback, pattern="^admin_"),
            CommandHandler("start", start_command),
            CommandHandler("admin", admin_panel),
        ],
        allow_reentry=True,
        per_message=False,
    )
    application.add_handler(conv)
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    application.add_handler(CommandHandler("admin", admin_panel))

    return application
