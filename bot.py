# فایل اصلی ربات تلگرام فرنود

from telegram.ext import (
    Application, CommandHandler, MessageHandler, PreCheckoutQueryHandler,
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
    admin_panel, admin_callback, receive_welcome_message, receive_admin_text,
    receive_user_field, WAITING_WELCOME, WAITING_USER_FIELD, WAITING_ADMIN_TEXT,
)
from handlers.buy import start_buy, buy_callback, receive_buy_receipt, receive_buy_custom_name, WAITING_BUY_CUSTOM_NAME, WAITING_BUY_RECEIPT
from handlers.services_user import (
    show_my_services, services_callback, show_support, support_callback,
    receive_ticket_subject, receive_ticket_msg, receive_ticket_reply, show_education,
    receive_rename,
    WAITING_TICKET_SUBJECT, WAITING_TICKET_MSG, WAITING_TICKET_REPLY, WAITING_RENAME,
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
        from db_extras import ensure_extras_tables, ensure_bot_admins_table
        ensure_extras_tables()
        ensure_bot_admins_table()
        from database import ensure_panel_max_sales
        ensure_panel_max_sales()
        from services.provision import ensure_service_template
        ensure_service_template()
    except Exception as e:
        print(f"user tables: {e}")
    try:
        from handlers.group_reports import backup_job, hourly_job, get_backup_interval_seconds, auto_approve_job
        jq = application.job_queue
        if jq:
            bsecs = get_backup_interval_seconds()
            jq.run_repeating(backup_job, interval=bsecs, first=60, name="db_backup")
            jq.run_repeating(hourly_job, interval=3600, first=120, name="hourly_charges")
            jq.run_repeating(auto_approve_job, interval=120, first=90, name="card_auto_approve")
            print(f"backup job every {bsecs/3600:.1f}h")
            # بهینه‌سازی خودکار
            try:
                from database import get_setting_sync
                opt_h = float(get_setting_sync("optimize_interval_hours", "0") or 0)
                if opt_h > 0:
                    opt_secs = max(3600, int(opt_h * 3600))
                    async def _auto_optimize_job(context):
                        try:
                            from services.optimize import optimize_bot_data, format_optimize_report
                            from config import ADMIN_ID
                            stats = optimize_bot_data()
                            msg = format_optimize_report(stats)
                            if ADMIN_ID:
                                await context.bot.send_message(ADMIN_ID, msg, parse_mode="HTML")
                        except Exception as e:
                            print("auto optimize:", e)
                    jq.run_repeating(_auto_optimize_job, interval=opt_secs, first=min(300, opt_secs), name="auto_optimize")
                    print(f"auto optimize every {opt_h}h")
            except Exception as e:
                print("auto optimize setup:", e)
    except Exception as e:
        print(f"jobs: {e}")

async def post_shutdown(application: Application):
    await close_db()

async def text_router(update, context):
    """مسیریابی دکمه‌های کیبورد اصلی"""
    text = (update.message.text or "").strip()
    uid = update.effective_user.id if update.effective_user else 0
    # لغو عملیات در انتظار اگر کاربر دکمه منوی دیگری را زد
    try:
        context.user_data.pop("premiji_step", None)
        context.user_data.pop("premiji_code", None)
    except Exception:
        pass
    # حذف نشانگر رنگ از متن کیبورد
    for pfx in ("🔵 ", "🟢 ", "🔴 ", "⚪ "):
        if text.startswith(pfx):
            text = text[len(pfx):].strip()
            break
    try:
        from db_extras import get_menu_buttons, strip_premium_codes
        for item in get_menu_buttons():
            if not item.get("enabled", True):
                continue
            raw = (item.get("label") or "").split("\n")[0].strip()
            clean = strip_premium_codes(raw)
            if text == raw or text == clean:
                cb = item.get("callback", "")
                if cb == "menu_buy": return await start_buy(update, context)
                if cb == "menu_services": return await show_my_services(update, context)
                if cb == "menu_wallet": return await show_wallet(update, context)
                if cb == "menu_trial": return await start_trial(update, context)
                if cb == "menu_support": return await show_support(update, context)
                if cb == "menu_education": return await show_education(update, context)
                if cb == "menu_reseller": return await start_reseller_request(update, context)
    except Exception:
        pass
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
    if text == "⚙️ مدیریت":
        from handlers.admin import is_admin
        if is_admin(uid):
            result = await admin_panel(update, context)
            # لینک مخزن کنار پنل مدیریت
            try:
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📂 گیت‌هاب پروژه", url="https://github.com/farnoudhosseini/FarnoudBot")],
                ])
                await context.bot.send_message(
                    uid,
                    "🔗 مخزن پروژه فرنود:\nhttps://github.com/farnoudhosseini/FarnoudBot",
                    reply_markup=kb,
                    disable_web_page_preview=True,
                )
            except Exception:
                pass
            return result
    return None


async def menu_callback(update, context):
    """مسیریابی منوی شیشه‌ای (اینلاین)"""
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    uid = update.effective_user.id if update.effective_user else 0
    # لغو عملیات در انتظار (ایموجی پریمیوم و ...) اگر کاربر به منوی دیگری رفت
    try:
        context.user_data.pop("premiji_step", None)
        context.user_data.pop("premiji_code", None)
    except Exception:
        pass
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
        result = await admin_panel(update, context)
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📂 گیت‌هاب پروژه", url="https://github.com/farnoudhosseini/FarnoudBot")],
            ])
            await context.bot.send_message(
                uid,
                "🔗 مخزن پروژه فرنود:\nhttps://github.com/farnoudhosseini/FarnoudBot",
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception:
            pass
        return result
    if data == "menu_home":
        # مستقیم مثل /start به منوی اصلی برود؛ متن «منوی اصلی» ارسال نشود
        try:
            await update.callback_query.answer()
        except Exception:
            pass
        try:
            # پیام قبلی را در صورت امکان حذف/پاک کنیم تا شلوغ نشود
            await update.callback_query.delete_message()
        except Exception:
            try:
                await update.callback_query.edit_message_text("‎")
            except Exception:
                pass
        from handlers.start import _send_welcome
        user = update.effective_user
        await _send_welcome(update, context, user)
        return None
    return None

def create_bot() -> Application:
    from middleware_antispam import install_antispam

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .concurrent_updates(True)  # پاسخ سریع‌تر به چند کاربر هم‌زمان
        .build()
    )
    install_antispam(application)

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("restart", start_command))
    application.add_handler(MessageHandler(
        filters.Regex(r"^/(استارت|restart|Restart|START)(@\w+)?(\s|$)"),
        start_command,
    ))
    application.add_handler(CallbackQueryHandler(check_join_callback, pattern="^check_join$"))
    application.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    application.add_handler(CommandHandler("admin", admin_panel))
    # هندلر اولویت‌دار برای ورودی‌های متنی ادمین (افزودن ادمین، شارژ دستی و ...) تا حتی اگر Conversation state ست نشده باشد کار کند
    async def _admin_text_fallback(update, context):
        from handlers.admin import is_admin, receive_admin_text
        from telegram.ext import ApplicationHandlerStop
        user = update.effective_user
        if user and is_admin(user.id) and context.user_data.get("admin_input_mode"):
            await receive_admin_text(update, context)
            raise ApplicationHandlerStop
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _admin_text_fallback), group=-1)
    application.add_handler(CommandHandler("wallet", show_wallet))
    from handlers.group_reports import setgroup_command, backup_command
    application.add_handler(CommandHandler("setgroup", setgroup_command))
    application.add_handler(CommandHandler("backup", backup_command))
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
    # خرید سرویس — بدون ConversationHandler برای جلوگیری از گیر کردن دکمه‌ها
    # همه callbackهای buy_ با هندلر ساده پردازش می‌شوند
    application.add_handler(CallbackQueryHandler(buy_callback, pattern="^buy_"))

    # دریافت نام سفارشی سرویس هنگام خرید (بر اساس user_data)
    async def _buy_custom_name_handler(update, context):
        if context.user_data.get("buy_pending_pid"):
            return await receive_buy_custom_name(update, context)
        return None
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, _buy_custom_name_handler),
        group=1,
    )

    # دریافت رسید خرید (بر اساس user_data، نه state مکالمه)
    async def _buy_receipt_handler(update, context):
        if context.user_data.get("waiting_buy_receipt"):
            return await receive_buy_receipt(update, context)
        return None
    application.add_handler(
        MessageHandler(filters.PHOTO | filters.Document.ALL, _buy_receipt_handler),
        group=1,
    )
    
    async def _support_cancel(update, context):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        context.user_data.pop("sup_ticket", None)
        context.user_data.pop("sup_dep", None)
        await update.message.reply_text(
            "✅ ارسال پیام لغو شد.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛠 پشتیبانی", callback_data="sup_back")],
                [InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_home")],
            ]),
        )
        return ConversationHandler.END

    support_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(support_callback, pattern="^sup_")],
        states={
            WAITING_TICKET_SUBJECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ticket_subject),
                CommandHandler("cancel", _support_cancel),
            ],
            WAITING_TICKET_MSG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ticket_msg),
                CommandHandler("cancel", _support_cancel),
            ],
            WAITING_TICKET_REPLY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ticket_reply),
                CommandHandler("cancel", _support_cancel),
            ],
        },
        fallbacks=[
            CommandHandler("start", start_command),
            CommandHandler("cancel", _support_cancel),
            CallbackQueryHandler(support_callback, pattern="^sup_"),
        ],
        allow_reentry=True,
        per_message=False,
    )
    application.add_handler(support_conv)
    application.add_handler(CallbackQueryHandler(support_callback, pattern="^sup_"))

    rename_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(services_callback, pattern="^svc_rename_")],
        states={
            WAITING_RENAME: [
                MessageHandler(filters.TEXT, receive_rename),
            ],
        },
        fallbacks=[
            CommandHandler("start", start_command),
            CommandHandler("cancel", start_command),
        ],
        allow_reentry=True,
        per_message=False,
    )
    application.add_handler(rename_conv)
    application.add_handler(CallbackQueryHandler(services_callback, pattern="^svc_"))

    application.add_handler(wallet_conv)
    application.add_handler(CallbackQueryHandler(wallet_callback, pattern="^(wallet_|pay_)"))

    # مکالمه ادمین (پیام خوش‌آمد + کاربران VPN + ورودی‌های متنی مثل افزودن ادمین)
    # entry_points شامل همه callbackهایی است که ممکن است به WAITING_ADMIN_TEXT بروند تا state درست ست شود
    admin_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                admin_callback,
                pattern="^(set_welcome|admin_msg_|admin_msgs|admin_products|admin_product_add|admin_menu_labels|admin_mblabel_|admin_msgs_tpl|admin_to_start|admin_pdelete|admin_padduser_|admin_pedit_|admin_ordedit_|admin_premiji_add|admin_user_search|admin_bc_|admin_web|admin_web_|admin_card_add|admin_pmax_|admin_prenew|admin_referral|admin_ref_|admin_welcome|admin_badm_|admin_botadmins|admin_stars_|admin_gift_|admin_trial_|admin_as_|admin_card_|admin_auto_|admin_charge_|admin_menu_|admin_prod_|admin_order_|admin_ticket_|admin_backup_|admin_inline_|admin_panel|admin_optimize|admin_settings|admin_users|admin_support)",
            ),
        ],
        states={
            WAITING_WELCOME: [MessageHandler(filters.TEXT, receive_welcome_message)],
            WAITING_USER_FIELD: [MessageHandler(filters.TEXT, receive_user_field)],
            WAITING_ADMIN_TEXT: [MessageHandler(filters.TEXT, receive_admin_text)],
        },
        fallbacks=[
            CallbackQueryHandler(admin_callback, pattern="^admin_"),
            CommandHandler("start", start_command),
            CommandHandler("cancel", admin_panel),
            CommandHandler("admin", admin_panel),
        ],
        allow_reentry=True,
        per_message=False,
    )
    application.add_handler(admin_conv)
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^(admin_|adm_ch_|adm_ord_|adm_ref_)"))

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


    # پرداخت استارز تلگرام (بازنویسی کامل ۰.۰.۷)
    async def _pre_checkout(update, context):
        q = update.pre_checkout_query
        payload = (q.invoice_payload or "") if q else ""
        try:
            # اعتبارسنجی اولیه payload
            if payload.startswith("order_stars_"):
                from db_products import get_order
                try:
                    oid = int(payload.replace("order_stars_", ""))
                except Exception:
                    await q.answer(ok=False, error_message="سفارش نامعتبر")
                    return
                order = get_order(oid)
                if not order:
                    await q.answer(ok=False, error_message="سفارش یافت نشد")
                    return
                if order.get("status") in ("paid", "provisioned"):
                    await q.answer(ok=False, error_message="این سفارش قبلاً پرداخت شده")
                    return
            elif payload.startswith("charge_stars_"):
                pass  # شارژ کیف پول — در successful تایید می‌شود
            else:
                await q.answer(ok=False, error_message="پرداخت نامعتبر")
                return
            await q.answer(ok=True)
        except Exception as e:
            print("pre_checkout:", e)
            try:
                await q.answer(ok=False, error_message="خطا در تایید پرداخت")
            except Exception:
                pass

    async def _successful_payment(update, context):
        msg = update.message
        sp = msg.successful_payment
        if not sp:
            return
        payload = sp.invoice_payload or ""
        stars_paid = int(sp.total_amount or 0)  # تعداد استارز

        # --- خرید سرویس با استارز ---
        if payload.startswith("order_stars_"):
            try:
                order_id = int(payload.replace("order_stars_", ""))
            except Exception:
                await msg.reply_text("❌ payload سفارش نامعتبر.")
                return
            from db_products import get_order, update_order
            from services.provision import provision_order, send_service_to_user
            order = get_order(order_id)
            if not order:
                await msg.reply_text("❌ سفارش یافت نشد.")
                return
            if order.get("status") in ("paid", "provisioned"):
                await msg.reply_text("ℹ️ این سفارش قبلاً پردازش شده است.")
                return
            # ثبت پرداخت
            update_order(
                order_id,
                status="paid",
                method_key="stars",
                pay_amount=int(order.get("pay_amount") or order.get("amount") or 0),
            )
            await msg.reply_text(
                f"✅ پرداخت <b>{stars_paid}</b> استارز تایید شد.\n⏳ در حال ساخت سرویس...",
                parse_mode="HTML",
            )
            result = provision_order(order_id)
            try:
                await send_service_to_user(context.bot, order["telegram_id"], result)
            except Exception as e:
                print("stars deliver:", e)
                if result.get("ok"):
                    await msg.reply_text("✅ سرویس ساخته شد. از «سرویس‌های من» ببینید.")
                else:
                    await msg.reply_text(f"❌ خطا در ساخت سرویس: {str(result.get('error') or e)[:200]}")
            if result.get("ok"):
                try:
                    from db_growth import award_purchase_points, pay_referral_commission
                    amt = int(order.get("amount") or 0)
                    award_purchase_points(order["telegram_id"], amt, order_id)
                    pay_referral_commission(order["telegram_id"], amt)
                except Exception:
                    pass
            return

        # --- شارژ کیف پول با استارز ---
        if payload.startswith("charge_stars_"):
            try:
                parts = payload.replace("charge_stars_", "").split("_")
                uid = int(parts[0])
                toman = int(parts[1]) if len(parts) > 1 else 0
            except Exception:
                await msg.reply_text("❌ payload شارژ نامعتبر.")
                return
            if uid != (msg.from_user.id if msg.from_user else 0):
                await msg.reply_text("❌ کاربر پرداخت با گیرنده مطابقت ندارد.")
                return
            if toman <= 0:
                # محاسبه از نرخ
                from database import get_setting_sync
                try:
                    rate = float(get_setting_sync("stars_rate", "1000") or 1000)
                except Exception:
                    rate = 1000.0
                toman = int(round(stars_paid * rate))
            try:
                from db_users import add_balance, upsert_bot_user
                upsert_bot_user(msg.from_user)
                add_balance(uid, toman, f"stars_charge#{stars_paid}")
                await msg.reply_text(
                    f"✅ شارژ موفق!\n"
                    f"⭐ {stars_paid} استارز → <b>{toman:,}</b> تومان به کیف پول اضافه شد.",
                    parse_mode="HTML",
                )
            except Exception as e:
                print("stars charge:", e)
                await msg.reply_text(f"❌ خطا در شارژ کیف پول: {str(e)[:200]}")
            return

        await msg.reply_text("ℹ️ پرداخت دریافت شد اما نوع آن شناسایی نشد.")

    application.add_handler(PreCheckoutQueryHandler(_pre_checkout))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, _successful_payment))


    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    return application
