# کیف پول، شارژ، کد هدیه، زیرمجموعه

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID, BOT_TOKEN
from db_users import (
    get_bot_user, upsert_bot_user, user_vars, render_template, log_activity,
    create_charge, get_charge, set_charge_receipt, list_cards, list_payment_methods,
    redeem_gift, count_referrals,
)
from database import get_setting_sync

WAITING_CHARGE_AMOUNT = 10
WAITING_GIFT_CODE = 11
WAITING_RECEIPT = 12

def main_user_keyboard(is_admin: bool = False):
    """Main menu from one configurable source: order, visibility and labels are persisted."""
    from database import get_setting_sync
    from db_extras import get_menu_buttons
    items=[x for x in get_menu_buttons() if x.get("enabled",True)]
    use_inline=get_setting_sync("inline_main_menu","0")=="1"
    def label(item):
        return (item.get("label") or item.get("key") or "—").split("\n")[0][:40]
    if use_inline:
        rows=[]
        row=[]
        for item in items:
            row.append(InlineKeyboardButton(label(item),callback_data=item.get("callback","menu_home")))
            if len(row)==2:
                rows.append(row); row=[]
        if row: rows.append(row)
        if is_admin: rows.append([InlineKeyboardButton("⚙️ مدیریت",callback_data="menu_admin")])
        return InlineKeyboardMarkup(rows)
    rows=[]; row=[]
    for item in items:
        row.append(KeyboardButton(label(item)))
        if len(row)==2: rows.append(row); row=[]
    if row: rows.append(row)
    if is_admin: rows.append([KeyboardButton("⚙️ مدیریت")])
    return ReplyKeyboardMarkup(rows,resize_keyboard=True)


def wallet_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 شارژ حساب", callback_data="wallet_charge")],
        [InlineKeyboardButton("🎁 کد هدیه", callback_data="wallet_gift")],
        [InlineKeyboardButton("👥 زیرمجموعه", callback_data="wallet_refs")],
    ])

def payment_methods_keyboard(charge_id: int):
    methods = list_payment_methods(active_only=True)
    rows = []
    for m in methods:
        rows.append([InlineKeyboardButton(m["title"], callback_data=f"pay_{m['method_key']}_{charge_id}")])
    rows.append([InlineKeyboardButton("❌ انصراف", callback_data="wallet_cancel")])
    return InlineKeyboardMarkup(rows)

async def _bot_username(context: ContextTypes.DEFAULT_TYPE) -> str:
    try:
        me = await context.bot.get_me()
        return me.username or ""
    except Exception:
        return ""

async def show_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bu = get_bot_user(user.id) or upsert_bot_user(user)
    uname = await _bot_username(context)
    text = render_template("wallet_main", user_vars(bu, uname))
    if update.message:
        await update.message.reply_text(text, reply_markup=wallet_keyboard())
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=wallet_keyboard())
    log_activity(user.id, "wallet_open")

async def wallet_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    user = update.effective_user
    bu = get_bot_user(user.id)
    if not bu:
        bu = upsert_bot_user(user)
    uname = await _bot_username(context)

    if data == "wallet_cancel":
        await show_wallet(update, context)
        return ConversationHandler.END

    if data == "wallet_charge":
        vars_ = user_vars(bu, uname)
        text = render_template("wallet_charge", vars_)
        await q.edit_message_text(text)
        return WAITING_CHARGE_AMOUNT

    if data == "wallet_gift":
        text = render_template("wallet_gift", user_vars(bu, uname))
        await q.edit_message_text(text)
        return WAITING_GIFT_CODE

    if data == "wallet_refs":
        text = render_template("wallet_referrals", user_vars(bu, uname))
        await q.edit_message_text(text, reply_markup=wallet_keyboard())
        return ConversationHandler.END

    if data.startswith("pay_card_"):
        charge_id = int(data.split("_")[-1])
        ch = get_charge(charge_id)
        if not ch or ch["telegram_id"] != user.id:
            await q.edit_message_text("فاکتور نامعتبر است.")
            return ConversationHandler.END
        cards = list_cards(active_only=True)
        if not cards:
            await q.edit_message_text("در حال حاضر کارتی تعریف نشده. با پشتیبانی تماس بگیرید.")
            return ConversationHandler.END
        card = cards[0]
        # ذخیره card_id
        from database import get_sync_connection
        conn = get_sync_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE charge_requests SET card_id=%s WHERE id=%s", (card["id"], charge_id))
                conn.commit()
        finally:
            conn.close()
        vars_ = user_vars(bu, uname)
        vars_["amount"] = f"{int(ch['amount']):,}"
        vars_["invoice_id"] = charge_id
        vars_["card_number"] = card["card_number"]
        vars_["card_owner"] = card["owner_name"]
        text = render_template("charge_card_info", vars_)
        await q.edit_message_text(text)
        context.user_data["waiting_receipt_charge_id"] = charge_id
        return WAITING_RECEIPT

    return ConversationHandler.END

async def receive_charge_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (update.message.text or "").replace(",", "").replace("،", "").strip()
    try:
        amount = int(text)
    except ValueError:
        await update.message.reply_text("مبلغ را به صورت عدد وارد کنید:")
        return WAITING_CHARGE_AMOUNT
    min_c = int(get_setting_sync("min_charge", "10000") or 10000)
    max_c = int(get_setting_sync("max_charge", "50000000") or 50000000)
    if amount < min_c or amount > max_c:
        await update.message.reply_text(f"مبلغ باید بین {min_c:,} و {max_c:,} تومان باشد:")
        return WAITING_CHARGE_AMOUNT
    charge_id = create_charge(user.id, amount, method_key="card")
    bu = get_bot_user(user.id)
    uname = await _bot_username(context)
    vars_ = user_vars(bu, uname)
    vars_["amount"] = f"{amount:,}"
    vars_["invoice_id"] = charge_id
    msg = render_template("charge_invoice", vars_)
    await update.message.reply_text(msg, reply_markup=payment_methods_keyboard(charge_id))
    log_activity(user.id, "charge_create", str(amount))
    return ConversationHandler.END

async def receive_gift_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    code = (update.message.text or "").strip()
    ok, msg, amount = redeem_gift(user.id, code)
    if ok:
        bu = get_bot_user(user.id)
        await update.message.reply_text(f"✅ {msg}\nمبلغ: {amount:,} تومان\nموجودی: {int(bu['balance']):,} تومان")
    else:
        await update.message.reply_text(f"❌ {msg}")
    return ConversationHandler.END

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    charge_id = context.user_data.get("waiting_receipt_charge_id")
    if not charge_id:
        return ConversationHandler.END
    file_id = None
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document:
        file_id = update.message.document.file_id
    else:
        await update.message.reply_text("لطفاً تصویر رسید را ارسال کنید.")
        return WAITING_RECEIPT
    set_charge_receipt(charge_id, file_id)
    bu = get_bot_user(user.id)
    uname = await _bot_username(context)
    vars_ = user_vars(bu, uname)
    vars_["invoice_id"] = charge_id
    vars_["amount"] = f"{int(get_charge(charge_id)['amount']):,}"
    await update.message.reply_text(render_template("charge_waiting", vars_))
    # اطلاع به ادمین
    try:
        await context.bot.send_message(
            ADMIN_ID,
            f"🧾 رسید جدید\nکاربر: {user.id}\nفاکتور: #{charge_id}\nمبلغ: {vars_['amount']}",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ تایید", callback_data=f"adm_ch_ok_{charge_id}"),
                    InlineKeyboardButton("❌ رد", callback_data=f"adm_ch_no_{charge_id}"),
                ]
            ]),
        )
        await context.bot.send_photo(ADMIN_ID, file_id, caption=f"رسید #{charge_id}")
    except Exception as e:
        print(f"notify admin: {e}")
    log_activity(user.id, "charge_receipt", str(charge_id))
    context.user_data.pop("waiting_receipt_charge_id", None)
    return ConversationHandler.END
