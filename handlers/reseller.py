# درخواست نمایندگی — کاربر درخواست می‌دهد، تایید فقط از وب‌پنل

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID
from database import get_setting_sync
from db_users import get_template, upsert_bot_user, get_bot_user, log_activity, render_template
from db_growth import (
    create_reseller_request, user_pending_reseller_request, get_reseller_request,
)

WAITING_RESELLER_DESC = 41

ROLE_LABEL = {
    "reseller": "نماینده عادی",
    "reseller_vip": "نماینده ویژه",
}


async def start_reseller_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع درخواست نمایندگی از منوی اصلی"""
    user = update.effective_user
    upsert_bot_user(user)

    if get_setting_sync("reseller_request_enabled", "1") != "1":
        msg = "درخواست نمایندگی فعلاً غیرفعال است."
        if update.message:
            await update.message.reply_text(msg)
        else:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(msg)
        return ConversationHandler.END

    bu = get_bot_user(user.id)
    role = (bu or {}).get("role") or "user"
    if role in ("reseller", "reseller_vip"):
        label = ROLE_LABEL.get(role, role)
        text = f"شما هم‌اکنون «{label}» هستید و نیازی به درخواست مجدد ندارید."
        if update.message:
            await update.message.reply_text(text)
        else:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text)
        return ConversationHandler.END

    pending = user_pending_reseller_request(user.id)
    if pending:
        text = f"⏳ شما یک درخواست در حال بررسی دارید (#{pending['id']}).\nلطفاً منتظر تایید ادمین بمانید."
        if update.message:
            await update.message.reply_text(text)
        else:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text)
        return ConversationHandler.END

    prompt = get_template("reseller_request_prompt") or (
        "🤝 درخواست نمایندگی\n\n"
        "توضیحات خود را بنویسید (سابقه فروش، تعداد مشتری، شهر و ...):\n"
        "پس از ارسال، درخواست در صف بررسی ادمین قرار می‌گیرد."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ انصراف", callback_data="reseller_cancel")],
        [InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_home")],
    ])
    if update.message:
        await update.message.reply_text(prompt, reply_markup=kb)
    else:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(prompt, reply_markup=kb)
    return WAITING_RESELLER_DESC


async def receive_reseller_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    desc = (update.message.text or "").strip()
    if not desc or len(desc) < 10:
        await update.message.reply_text("توضیحات خیلی کوتاه است. حداقل چند جمله بنویسید:")
        return WAITING_RESELLER_DESC

    rid = create_reseller_request(user.id, desc)
    if rid < 0:
        await update.message.reply_text(
            f"⏳ شما قبلاً درخواست #{abs(rid)} را ثبت کرده‌اید و در انتظار بررسی است."
        )
        return ConversationHandler.END

    log_activity(user.id, "reseller_request", f"id={rid}")
    text = render_template("reseller_request_sent", {"request_id": rid}) or (
        f"✅ درخواست نمایندگی شما ثبت شد و در انتظار بررسی ادمین است.\nشماره درخواست: #{rid}"
    )
    await update.message.reply_text(text)

    # اطلاع به ادمین
    try:
        name = " ".join(filter(None, [user.first_name, user.last_name])) or user.username or str(user.id)
        await context.bot.send_message(
            ADMIN_ID,
            f"🤝 درخواست نمایندگی جدید #{rid}\n"
            f"کاربر: {name} ({user.id})\n"
            f"@{user.username or '—'}\n\n"
            f"{desc[:800]}\n\n"
            f"برای تایید/رد به وب‌پنل → درخواست‌های نمایندگی مراجعه کنید.",
        )
    except Exception:
        pass
    return ConversationHandler.END


async def cancel_reseller(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لغو درخواست نمایندگی و بستن state مکالمه (از دکمه، /cancel یا خروج به منو)."""
    context.user_data.pop("reseller_request", None)
    # پاک‌کردن هر state مرتبط تا دیگر منتظر توضیحات نماند
    for k in list(context.user_data.keys()):
        if k.startswith("reseller"):
            context.user_data.pop(k, None)
    q = update.callback_query
    if q:
        try:
            await q.answer("لغو شد.")
        except Exception:
            pass
        data = (q.data or "")
        # اگر کاربر به منوی دیگری رفت، فقط state را ببند و پیام لغو نشان نده
        if data.startswith("menu_") and data != "menu_reseller":
            return ConversationHandler.END
        try:
            await q.edit_message_text(
                "❌ درخواست نمایندگی لغو شد.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_home")]]),
            )
        except Exception:
            try:
                await q.message.reply_text(
                    "❌ درخواست نمایندگی لغو شد.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_home")]]),
                )
            except Exception:
                pass
    elif update.message:
        await update.message.reply_text(
            "❌ درخواست نمایندگی لغو شد.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_home")]]),
        )
    return ConversationHandler.END
