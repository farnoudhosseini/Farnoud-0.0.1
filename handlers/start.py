from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from config import ADMIN_ID
from database import get_setting, get_setting_sync
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
    referrer_id = None
    if context.args:
        code = context.args[0].strip()
        ref = get_bot_user_by_invite(code)
        if ref:
            referrer_id = ref["telegram_id"]
    upsert_bot_user(user, referrer_id=referrer_id)
    log_activity(user.id, "start")

    # force join
    if get_setting_sync("force_join_enabled", "0") == "1":
        ch = get_setting_sync("force_join_channel", "")
        if ch and not await check_channel_member(context.bot, user.id, ch):
            msg = await get_setting("force_join_msg") or f"ابتدا در کانال عضو شوید:\n{ch}"
            msg = msg.replace("[channel]", ch)
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{ch.lstrip('@')}" if not ch.lstrip('-').isdigit() else f"https://t.me/c/{str(ch).lstrip('-')}")],
                [InlineKeyboardButton("✅ بررسی عضویت", callback_data="check_join")],
            ])
            await update.message.reply_text(msg, reply_markup=kb)
            return

    # force phone
    if get_setting_sync("force_phone_enabled", "0") == "1":
        bu = get_bot_user(user.id)
        if not bu or not bu.get("phone"):
            msg = await get_setting("force_phone_msg") or "شماره موبایل را ارسال کنید:"
            kb = ReplyKeyboardMarkup(
                [[KeyboardButton("📱 ارسال شماره", request_contact=True)]],
                resize_keyboard=True, one_time_keyboard=True,
            )
            await update.message.reply_text(msg, reply_markup=kb)
            return

    await _send_welcome(update, context, user)

async def _send_welcome(update, context, user):
    welcome = await get_setting("welcome_message", "سلام! به ربات فرنود خوش آمدید 👋")
    is_adm = user and user.id == ADMIN_ID
    target = update.message or update.callback_query.message
    await context.bot.send_message(
        user.id,
        welcome,
        reply_markup=main_user_keyboard(is_admin=is_adm),
        parse_mode="HTML",
    )
    if is_adm:
        await context.bot.send_message(
            user.id,
            "⚙️ دسترسی ادمین فعال است.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ مدیریت", callback_data="admin_panel")]]),
        )

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
