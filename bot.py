# فایل اصلی ربات تلگرام فرنود

from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters,
)
from config import BOT_TOKEN, ADMIN_ID
from database import init_db, close_db
from db_users import ensure_user_tables
from handlers.start import start_command
from handlers.admin import (
    admin_panel, admin_callback, receive_welcome_message,
    receive_user_field, WAITING_WELCOME, WAITING_USER_FIELD,
)
from handlers.wallet import (
    show_wallet, wallet_callback, receive_charge_amount,
    receive_gift_code, receive_receipt,
    WAITING_CHARGE_AMOUNT, WAITING_GIFT_CODE, WAITING_RECEIPT,
    main_user_keyboard,
)

async def post_init(application: Application):
    await init_db()
    try:
        ensure_user_tables()
    except Exception as e:
        print(f"user tables: {e}")

async def post_shutdown(application: Application):
    await close_db()

async def text_router(update, context):
    """مسیریابی دکمه‌های کیبورد اصلی"""
    text = (update.message.text or "").strip()
    uid = update.effective_user.id if update.effective_user else 0
    if text == "💰 کیف پول من":
        return await show_wallet(update, context)
    if text == "⚙️ مدیریت" and uid == ADMIN_ID:
        return await admin_panel(update, context)
    return None

def create_bot() -> Application:
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("wallet", show_wallet))

    # مکالمه کیف پول / شارژ / هدیه / رسید
    wallet_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(wallet_callback, pattern="^(wallet_|pay_)"),
        ],
        states={
            WAITING_CHARGE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_charge_amount)],
            WAITING_GIFT_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_gift_code)],
            WAITING_RECEIPT: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, receive_receipt),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_receipt),
            ],
        },
        fallbacks=[
            CommandHandler("start", start_command),
            CallbackQueryHandler(wallet_callback, pattern="^wallet_"),
        ],
        allow_reentry=True,
        per_message=False,
    )
    application.add_handler(wallet_conv)
    application.add_handler(CallbackQueryHandler(wallet_callback, pattern="^(wallet_|pay_)"))

    # مکالمه ادمین (پیام خوش‌آمد + کاربران VPN)
    admin_conv = ConversationHandler(
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
    application.add_handler(admin_conv)
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^(admin_|adm_ch_)"))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    return application
