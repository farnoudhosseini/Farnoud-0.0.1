from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
import asyncio
import re
from config import ADMIN_ID
from database import get_setting, get_setting_sync, get_settings_sync
from db_users import upsert_bot_user, get_bot_user_by_invite, log_activity, update_bot_user, get_bot_user
from handlers.wallet import main_user_keyboard

async def check_channel_member(bot, user_id: int, channel: str) -> bool:
    if not channel:
        return True
    try:
        chat_id = channel if channel.startswith("@") or channel.startswith("-") else f"@{channel.lstrip('@')}"
        # numeric id
        if channel.lstrip("-").isdigit():
            chat_id = int(channel)
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in ("member", "administrator", "creator")
    except Exception as e:
        print("channel check", e)
        return False

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not update.message:
        return

    # لغو عملیات‌های در انتظار (مثل افزودن ایموجی پریمیوم)
    try:
        context.user_data.pop("premiji_step", None)
        context.user_data.pop("premiji_code", None)
    except Exception:
        pass

    # تنظیمات مسیر START با یک query/connection و بدون بلاک کردن event loop.
    defaults = {
        "welcome_message": "سلام! به ربات فرنود خوش آمدید 👋",
        "force_join_enabled": "0",
        "force_join_channel": "",
        "force_join_msg": "",
        "force_phone_enabled": "0",
        "force_phone_msg": "",
        "inline_main_menu": "0",
    }
    try:
        settings = await asyncio.to_thread(
            get_settings_sync, list(defaults.keys()), defaults
        )
    except Exception:
        settings = defaults

    # ثبت/به‌روزرسانی کاربر. نتیجه upsert را نگه می‌داریم تا دوباره SELECT نزنیم.
    referrer_id = None
    bu = None
    try:
        if context.args:
            code = context.args[0].strip()
            ref = await asyncio.to_thread(get_bot_user_by_invite, code)
            if ref:
                referrer_id = ref["telegram_id"]
        bu = await asyncio.to_thread(upsert_bot_user, user, referrer_id)
        # لاگ برای نمایش Start لازم نیست؛ پس پاسخ را معطل نمی‌کند.
        try:
            asyncio.create_task(asyncio.to_thread(log_activity, user.id, "start"))
        except Exception:
            pass
    except Exception as e:
        print("start upsert/log:", e)

    # force join
    if settings.get("force_join_enabled", "0") == "1":
        ch = settings.get("force_join_channel", "")
        if ch and not await check_channel_member(context.bot, user.id, ch):
            msg = settings.get("force_join_msg", "") or f"ابتدا در کانال عضو شوید:\n{ch}"
            msg = msg.replace("[channel]", ch)
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "📢 عضویت در کانال",
                    url=f"https://t.me/{ch.lstrip('@')}" if not ch.lstrip('-').isdigit()
                    else f"https://t.me/c/{str(ch).lstrip('-')}"
                )],
                [InlineKeyboardButton("✅ بررسی عضویت", callback_data="check_join")],
            ])
            await update.message.reply_text(msg, reply_markup=kb)
            return

    # force phone
    if settings.get("force_phone_enabled", "0") == "1":
        if not bu or not bu.get("phone"):
            msg = settings.get("force_phone_msg", "") or "شماره موبایل را ارسال کنید:"
            kb = ReplyKeyboardMarkup(
                [[KeyboardButton("📱 ارسال شماره", request_contact=True)]],
                resize_keyboard=True, one_time_keyboard=True,
            )
            await update.message.reply_text(msg, reply_markup=kb)
            return

    await _send_welcome(
        update, context, user,
        user_row=bu,
        welcome=settings.get("welcome_message") or defaults["welcome_message"],
        inline_main_menu=settings.get("inline_main_menu", "0"),
    )


async def _send_welcome(update, context, user, user_row=None,
                        welcome=None, inline_main_menu=None):
    # استارت پرتکرار است؛ تنظیمات را از مسیر start_command می‌گیریم.
    if welcome is None:
        welcome = await asyncio.to_thread(
            get_setting_sync, "welcome_message", "سلام! به ربات فرنود خوش آمدید 👋"
        )
    welcome = welcome or "سلام! به ربات فرنود خوش آمدید 👋"

    try:
        from db_users import user_vars
        from db_extras import apply_premium_emojis
        u = user_row
        if u is None:
            u = await asyncio.to_thread(get_bot_user, user.id) or {}

        # فقط وقتی واقعاً متغیر وجود دارد، queryهای user_vars اجرا شوند.
        if re.search(r"\[[a-zA-Z_][a-zA-Z0-9_]*\]", welcome):
            welcome_vars = await asyncio.to_thread(user_vars, u)
            for k, v in welcome_vars.items():
                welcome = welcome.replace(f"[{k}]", str(v))

        # ایموجی پریمیوم فقط در صورت وجود کد، نه برای هر /start.
        if re.search(r"(?:p_[A-Za-z0-9_]+|\{\{premium:|\[p_)", welcome, re.I):
            welcome = await asyncio.to_thread(apply_premium_emojis, welcome)
    except Exception:
        pass

    is_adm = user and is_admin_user(user.id)
    use_glass = (
        inline_main_menu == "1"
        if inline_main_menu is not None
        else await asyncio.to_thread(get_setting_sync, "inline_main_menu", "0") == "1"
    )

    if use_glass:
        glass = main_user_keyboard(is_admin=is_adm, force_inline=True)
        try:
            await context.bot.send_message(
                user.id, "‎", reply_markup=ReplyKeyboardRemove()
            )
        except Exception:
            pass
        await context.bot.send_message(
            user.id, welcome, reply_markup=glass, parse_mode="HTML"
        )
    else:
        reply_kb = main_user_keyboard(is_admin=is_adm, force_inline=False)
        await context.bot.send_message(
            user.id, welcome, reply_markup=reply_kb, parse_mode="HTML"
        )
        if is_adm:
            await context.bot.send_message(
                user.id,
                "⚙️ دسترسی ادمین فعال است.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⚙️ مدیریت", callback_data="admin_panel")]]
                ),
            )


def is_admin_user(uid: int) -> bool:
    try:
        from handlers.admin import is_admin
        return is_admin(uid)
    except Exception:
        from config import ADMIN_ID
        return uid == ADMIN_ID



async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    ch = get_setting_sync("force_join_channel", "")
    if await check_channel_member(context.bot, user.id, ch):
        await q.edit_message_text("✅ عضویت تایید شد.")
        # phone next?
        if get_setting_sync("force_phone_enabled", "0") == "1":
            bu = get_bot_user(user.id)
            if not bu or not bu.get("phone"):
                msg = get_setting_sync("force_phone_msg", "شماره را ارسال کنید:")
                kb = ReplyKeyboardMarkup(
                    [[KeyboardButton("📱 ارسال شماره", request_contact=True)]],
                    resize_keyboard=True, one_time_keyboard=True,
                )
                await context.bot.send_message(user.id, msg, reply_markup=kb)
                return
        await _send_welcome(update, context, user)
    else:
        await q.answer("هنوز عضو کانال نیستید.", show_alert=True)

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    contact = update.message.contact
    if not contact or contact.user_id != user.id:
        await update.message.reply_text("لطفاً با دکمه، شماره خودتان را بفرستید.")
        return
    phone = contact.phone_number
    update_bot_user(user.id, phone=phone)
    await update.message.reply_text("✅ شماره ثبت شد.", reply_markup=ReplyKeyboardRemove())
    await _send_welcome(update, context, user)
