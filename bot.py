# فایل اصلی ربات تلگرام فرنود

from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters,
)
from config import BOT_TOKEN, ADMIN_ID
from database import init_db, close_db
from db_users import ensure_user_tables
from db_products import ensure_product_tables
from handlers.start import start_command, check_join_callback, contact_handler
from handlers.trial import start_trial
from db_growth import ensure_growth_tables
from handlers.admin import (
    admin_panel, admin_callback, receive_welcome_message,
    receive_user_field, WAITING_WELCOME, WAITING_USER_FIELD,
)
from handlers.buy import start_buy, buy_callback, receive_buy_receipt, WAITING_BUY_RECEIPT
from handlers.services_user import (
    show_my_services, services_callback, show_support, support_callback,
    receive_ticket_subject, receive_ticket_msg, receive_ticket_reply, show_education,
    WAITING_TICKET_SUBJECT, WAITING_TICKET_MSG, WAITING_TICKET_REPLY,
)
from db_support import ensure_support_tables
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
        ensure_product_tables()
        ensure_support_tables()
        ensure_growth_tables()
        from services.provision import ensure_service_template
        ensure_service_template()
    except Exception as e:
        print(f"user tables: {e}")

async def post_shutdown(application: Application):
    await close_db()

async def text_router(update, context):
    """مسیریابی دکمه‌های کیبورد اصلی"""
    text = (update.message.text or "").strip()
    uid = update.effective_user.id if update.effective_user else 0
    if "کیف پول" in text:
        return await show_wallet(update, context)
    if "خرید" in text:
        return await start_buy(update, context)
    if "سرویس" in text and "خرید" not in text:
        return await show_my_services(update, context)
    if "پشتیبانی" in text:
        return await show_support(update, context)
    if "آموزش" in text:
        return await show_education(update, context)
    if "تست" in text or "رایگان" in text:
        return await start_trial(update, context)
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
    application.add_handler(CallbackQueryHandler(check_join_callback, pattern="^check_join$"))
    application.add_handler(MessageHandler(filters.CONTACT, contact_handler))
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
    buy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_callback, pattern="^(buy_)")],
        states={
            WAITING_BUY_RECEIPT: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, receive_buy_receipt),
            ],
        },
        fallbacks=[CommandHandler("start", start_command)],
        allow_reentry=True,
        per_message=False,
    )
    application.add_handler(buy_conv)
    application.add_handler(CallbackQueryHandler(buy_callback, pattern="^buy_"))
    
    support_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(support_callback, pattern="^sup_")],
        states={
            WAITING_TICKET_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ticket_subject)],
            WAITING_TICKET_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ticket_msg)],
            WAITING_TICKET_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ticket_reply)],
        },
        fallbacks=[CommandHandler("start", start_command)],
        allow_reentry=True,
        per_message=False,
    )
    application.add_handler(support_conv)
    application.add_handler(CallbackQueryHandler(support_callback, pattern="^sup_"))
    application.add_handler(CallbackQueryHandler(services_callback, pattern="^svc_"))

    application.add_handler(wallet_conv)
    application.add_handler(CallbackQueryHandler(wallet_callback, pattern="^(wallet_|pay_)"))

    # مکالمه ادمین (پیام خوش‌آمد + کاربران VPN)
    admin_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_callback, pattern="^(set_welcome|admin_msg_|admin_msgs|admin_products|admin_padduser_|admin_pedit_)"),
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
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^(admin_|adm_ch_|adm_ord_)"))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    return application
