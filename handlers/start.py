from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_ID
from database import get_setting
from db_users import upsert_bot_user, get_bot_user_by_invite, log_activity
from handlers.wallet import main_user_keyboard

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

    welcome = await get_setting("welcome_message", "سلام! به ربات فرنود خوش آمدید 👋")
    is_adm = user and user.id == ADMIN_ID
    await update.message.reply_text(
        welcome,
        reply_markup=main_user_keyboard(is_admin=is_adm),
        parse_mode="HTML",
    )
    if is_adm:
        await update.message.reply_text(
            "⚙️ دسترسی ادمین فعال است. از دکمه مدیریت یا /admin استفاده کنید.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ مدیریت", callback_data="admin_panel")]
            ]),
        )
