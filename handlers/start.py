# هندلر دستور /start

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_ID
from database import get_setting

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    پاسخ به دستور /start
    پیام خوش‌آمدگویی از دیتابیس خوانده می‌شود
    اگر کاربر ادمین باشد، دکمه مدیریت هم نمایش داده می‌شود
    """
    user = update.effective_user
    welcome = await get_setting("welcome_message", "سلام! به ربات فرنود خوش آمدید 👋")

    # اگر ادمین باشد، دکمه مدیریت اضافه شود
    keyboard = None
    if user and user.id == ADMIN_ID:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ مدیریت", callback_data="admin_panel")]
        ])

    await update.message.reply_text(
        welcome,
        reply_markup=keyboard,
        parse_mode="HTML",
    )
