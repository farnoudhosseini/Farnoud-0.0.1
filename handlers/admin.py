# پنل مدیریت داخل ربات تلگرام
# فقط برای ادمین اصلی قابل دسترسی است

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID
from database import get_setting, set_setting

# حالت مکالمه برای دریافت پیام خوش‌آمدگویی جدید
WAITING_WELCOME = 1

def is_admin(user_id: int) -> bool:
    """بررسی اینکه کاربر ادمین است یا نه"""
    return user_id == ADMIN_ID

def admin_keyboard():
    """کیبورد اصلی پنل مدیریت داخل ربات"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 تنظیم پیام خوش‌آمدگویی", callback_data="set_welcome")],
        [InlineKeyboardButton("📄 مشاهده پیام فعلی", callback_data="admin_view_welcome")],
        [InlineKeyboardButton("🔙 بستن", callback_data="admin_close")],
    ])

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """باز کردن پنل مدیریت با دستور /admin یا دکمه"""
    user = update.effective_user
    if not user or not is_admin(user.id):
        if update.message:
            await update.message.reply_text("⛔️ شما دسترسی به این بخش را ندارید.")
        return

    text = (
        "⚙️ <b>پنل مدیریت فرنود</b>\n\n"
        "از دکمه‌های زیر برای مدیریت ربات استفاده کنید."
    )

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text, reply_markup=admin_keyboard(), parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            text, reply_markup=admin_keyboard(), parse_mode="HTML"
        )

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت دکمه‌های پنل ادمین"""
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if not user or not is_admin(user.id):
        await query.edit_message_text("⛔️ دسترسی ندارید.")
        return ConversationHandler.END

    data = query.data

    # باز کردن پنل
    if data == "admin_panel":
        await admin_panel(update, context)
        return ConversationHandler.END

    # مشاهده پیام فعلی
    if data == "admin_view_welcome":
        current = await get_setting("welcome_message", "—")
        await query.edit_message_text(
            f"📄 <b>پیام خوش‌آمدگویی فعلی:</b>\n\n{current}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]
            ]),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    # شروع تنظیم پیام جدید
    if data == "set_welcome":
        await query.edit_message_text(
            "📝 لطفاً پیام خوش‌آمدگویی جدید را ارسال کنید.\n\n"
            "می‌توانید از HTML ساده استفاده کنید (مثل &lt;b&gt;متن&lt;/b&gt;).\n\n"
            "برای انصراف /start را بزنید.",
            parse_mode="HTML",
        )
        return WAITING_WELCOME

    # بستن پنل
    if data == "admin_close":
        await query.edit_message_text("✅ پنل مدیریت بسته شد.")
        return ConversationHandler.END

    # بازگشت به پنل
    if data == "admin_back":
        await admin_panel(update, context)
        return ConversationHandler.END

    return ConversationHandler.END

async def receive_welcome_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت و ذخیره پیام خوش‌آمدگویی جدید از ادمین"""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return ConversationHandler.END

    new_message = update.message.text.strip()
    if not new_message:
        await update.message.reply_text("❌ پیام نمی‌تواند خالی باشد. دوباره ارسال کنید.")
        return WAITING_WELCOME

    await set_setting("welcome_message", new_message)
    await update.message.reply_text(
        "✅ پیام خوش‌آمدگویی با موفقیت ذخیره شد.\n\n"
        f"📄 پیام جدید:\n{new_message}",
        reply_markup=admin_keyboard(),
        parse_mode="HTML",
    )
    return ConversationHandler.END
