# خرید سرویس جدید

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import list_panels, get_panel_by_id, get_setting_sync
from db_users import get_bot_user, upsert_bot_user, user_vars, render_template, log_activity, add_balance
from db_products import (
    list_categories, list_products, get_product, create_order, get_order, update_order,
)
from handlers.wallet import payment_methods_keyboard
from db_users import list_cards, create_charge, set_charge_receipt
from config import ADMIN_ID

WAITING_BUY_RECEIPT = 20

async def start_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_bot_user(user)
    panels = list_panels()
    if not panels:
        msg = "فعلاً پنلی برای خرید فعال نیست."
        if update.message:
            await update.message.reply_text(msg)
        else:
            await update.callback_query.edit_message_text(msg)
        return ConversationHandler.END
    rows = [[InlineKeyboardButton(p["name"], callback_data=f"buy_panel_{p['id']}")] for p in panels]
    rows.append([InlineKeyboardButton("❌ انصراف", callback_data="buy_cancel")])
    text = render_template("buy_select_panel", {}) or "🖥 پنل مورد نظر را انتخاب کنید:"
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(rows))
    else:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))
    log_activity(user.id, "buy_start")
    return ConversationHandler.END

async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    user = update.effective_user
    bu = get_bot_user(user.id) or upsert_bot_user(user)

    if data == "buy_cancel":
        await q.edit_message_text("خرید لغو شد.")
        return ConversationHandler.END

    if data.startswith("buy_panel_"):
        panel_id = int(data.replace("buy_panel_", ""))
        context.user_data["buy_panel_id"] = panel_id
        cats = list_categories(active_only=True)
        # فقط دسته‌هایی که محصول روی این پنل دارند
        products = list_products(panel_id=panel_id, role=bu.get("role"), active_only=True)
        cat_ids = {p.get("category_id") for p in products if p.get("category_id")}
        cats = [c for c in cats if c["id"] in cat_ids] or cats
        if not products:
            await q.edit_message_text("برای این پنل محصولی تعریف نشده.")
            return ConversationHandler.END
        if cats:
            rows = [[InlineKeyboardButton(c["name"], callback_data=f"buy_cat_{c['id']}")] for c in cats]
            rows.append([InlineKeyboardButton("همه محصولات", callback_data="buy_cat_0")])
            rows.append([InlineKeyboardButton("🔙 انصراف", callback_data="buy_cancel")])
            text = render_template("buy_select_category", {}) or "📁 دسته را انتخاب کنید:"
            await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))
        else:
            # مستقیم محصولات
            return await _show_products(q, context, panel_id, None, bu)
        return ConversationHandler.END

    if data.startswith("buy_cat_"):
        cat_id = int(data.replace("buy_cat_", ""))
        panel_id = context.user_data.get("buy_panel_id")
        return await _show_products(q, context, panel_id, cat_id if cat_id else None, bu)

    if data.startswith("buy_prod_"):
        pid = int(data.replace("buy_prod_", ""))
        product = get_product(pid)
        panel_id = context.user_data.get("buy_panel_id")
        panel = get_panel_by_id(panel_id) if panel_id else None
        if not product or not panel:
            await q.edit_message_text("محصول نامعتبر.")
            return ConversationHandler.END
        price = int(product["price"] or 0)
        balance = int(bu.get("balance") or 0)
        wallet_used = min(balance, price)
        pay_amount = max(0, price - balance)
        order_id = create_order(user.id, pid, panel_id, price, wallet_used, pay_amount)
        context.user_data["buy_order_id"] = order_id
        vars_ = {
            "product_name": product["name"],
            "panel_name": panel["name"],
            "price": f"{price:,}",
            "balance": f"{balance:,}",
            "pay_amount": f"{pay_amount:,}",
            "description": product.get("description") or "",
            "volume_gb": product.get("volume_gb"),
            "duration_days": product.get("duration_days"),
        }
        text = render_template("buy_invoice", vars_)
        if pay_amount <= 0:
            # پرداخت کامل از کیف پول
            add_balance(user.id, -wallet_used, f"order#{order_id}")
            update_order(order_id, status="paid", wallet_used=wallet_used, pay_amount=0)
            await q.edit_message_text(
                text + "\n\n✅ از موجودی کیف پول کسر شد.\nسرویس به‌زودی فعال می‌شود (تایید ادمین / ساخت خودکار در آپدیت بعدی).",
            )
            try:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"🛒 سفارش جدید #{order_id}\nکاربر: {user.id}\nمحصول: {product['name']}\nپرداخت از کیف پول",
                )
            except Exception:
                pass
            log_activity(user.id, "buy_paid_wallet", str(order_id))
            return ConversationHandler.END
        # نیاز به پرداخت باقیمانده
        kb = payment_methods_keyboard(order_id)
        # reuse pay_card with order - we'll handle buy_pay_
        rows = [[InlineKeyboardButton("💳 کارت به کارت", callback_data=f"buy_pay_card_{order_id}")]]
        rows.append([InlineKeyboardButton("❌ انصراف", callback_data="buy_cancel")])
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))
        return ConversationHandler.END

    if data.startswith("buy_pay_card_"):
        order_id = int(data.replace("buy_pay_card_", ""))
        order = get_order(order_id)
        if not order or order["telegram_id"] != user.id:
            await q.edit_message_text("سفارش نامعتبر.")
            return ConversationHandler.END
        cards = list_cards(active_only=True)
        if not cards:
            await q.edit_message_text("کارتی تعریف نشده.")
            return ConversationHandler.END
        card = cards[0]
        update_order(order_id, method_key="card", card_id=card["id"], status="waiting_receipt")
        # کسر کیف پول در تایید نهایی
        text = (
            f"💳 مبلغ {int(order['pay_amount']):,} تومان را به کارت زیر واریز کنید:\n\n"
            f"شماره: `{card['card_number']}`\n"
            f"به نام: {card['owner_name']}\n\n"
            f"سپس تصویر رسید را ارسال کنید."
        )
        await q.edit_message_text(text, parse_mode="Markdown")
        context.user_data["waiting_buy_receipt"] = order_id
        return WAITING_BUY_RECEIPT

    return ConversationHandler.END

async def _show_products(q, context, panel_id, cat_id, bu):
    products = list_products(
        category_id=cat_id if cat_id else None,
        panel_id=panel_id,
        role=bu.get("role"),
        active_only=True,
    )
    if not products:
        await q.edit_message_text("محصولی در این دسته نیست.")
        return ConversationHandler.END
    rows = []
    for p in products:
        rows.append([InlineKeyboardButton(
            f"{p['name']} — {int(p['price']):,} ت",
            callback_data=f"buy_prod_{p['id']}",
        )])
    rows.append([InlineKeyboardButton("🔙 انصراف", callback_data="buy_cancel")])
    text = render_template("buy_select_product", {}) or "📦 محصول را انتخاب کنید:"
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))
    return ConversationHandler.END

async def receive_buy_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    order_id = context.user_data.get("waiting_buy_receipt")
    if not order_id:
        return ConversationHandler.END
    file_id = None
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document:
        file_id = update.message.document.file_id
    else:
        await update.message.reply_text("تصویر رسید را بفرستید.")
        return WAITING_BUY_RECEIPT
    update_order(order_id, receipt_file_id=file_id, status="pending_review")
    await update.message.reply_text("⏳ رسید ثبت شد و در انتظار تایید ادمین است.")
    try:
        await context.bot.send_message(
            ADMIN_ID,
            f"🧾 رسید سفارش #{order_id}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ تایید سفارش", callback_data=f"adm_ord_ok_{order_id}"),
                InlineKeyboardButton("❌ رد", callback_data=f"adm_ord_no_{order_id}"),
            ]]),
        )
        await context.bot.send_photo(ADMIN_ID, file_id, caption=f"رسید سفارش #{order_id}")
    except Exception as e:
        print(e)
    context.user_data.pop("waiting_buy_receipt", None)
    return ConversationHandler.END
