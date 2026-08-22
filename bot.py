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
from handlers.trial import start_trial, trial_callback
from handlers.reseller import (
    start_reseller_request, receive_reseller_desc, cancel_reseller, WAITING_RESELLER_DESC,
)
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
        from db_products import ensure_service_mgmt_columns
        ensure_service_mgmt_columns()
        from db_extras import ensure_extras_tables
        ensure_extras_tables()
        from database import ensure_panel_max_sales
        ensure_panel_max_sales()
        from services.provision import ensure_service_template
        ensure_service_template()
    except Exception as e:
        print(f"user tables: {e}")
    try:
        from handlers.group_reports import backup_job, hourly_job
        jq = application.job_queue
        if jq:
            jq.run_repeating(backup_job, interval=7200, first=60)
            jq.run_repeating(hourly_job, interval=3600, first=120)
    except Exception as e:
        print(f"jobs: {e}")

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


async def menu_callback(update, context):
    """مسیریابی منوی شیشه‌ای (اینلاین)"""
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    uid = update.effective_user.id if update.effective_user else 0
    if data == "menu_wallet":
        return await show_wallet(update, context)
    if data == "menu_buy":
        return await start_buy(update, context)
    if data == "menu_services":
        return await show_my_services(update, context)
    if data == "menu_support":
        return await show_support(update, context)
    if data == "menu_education":
        return await show_education(update, context)
    if data == "menu_trial":
        return await start_trial(update, context)
    if data == "menu_reseller":
        return await start_reseller_request(update, context)
    if data == "menu_admin" and uid == ADMIN_ID:
        return await admin_panel(update, context)
    if data == "menu_home":
        from handlers.start import start_command
        # fake message path - send main keyboard
        from handlers.wallet import main_user_keyboard
        await update.callback_query.edit_message_text("🏠 منوی اصلی", reply_markup=main_user_keyboard(is_admin=(uid==ADMIN_ID)))
        return None
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
    from handlers.group_reports import setgroup_command
    application.add_handler(CommandHandler("setgroup", setgroup_command))
    application.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu_"))
    application.add_handler(CallbackQueryHandler(trial_callback, pattern="^trial_"))

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
            CallbackQueryHandler(admin_callback, pattern="^(set_welcome|admin_msg_|admin_msgs|admin_products|admin_padduser_|admin_pedit_|admin_ordedit_|admin_premiji_add)"),
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

    # درخواست نمایندگی
    reseller_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.TEXT & filters.Regex(r"نمایندگی|نماینده"),
                start_reseller_request,
            ),
        ],
        states={
            WAITING_RESELLER_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_reseller_desc),
            ],
        },
        fallbacks=[
            CommandHandler("start", start_command),
            CommandHandler("cancel", cancel_reseller),
        ],
        allow_reentry=True,
        per_message=False,
    )
    application.add_handler(reseller_conv)

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    return application
