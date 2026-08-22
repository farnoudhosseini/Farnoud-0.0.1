# خرید سرویس جدید + تحویل خودکار

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import list_panels, get_panel_by_id
from db_users import (
    get_bot_user, upsert_bot_user, render_template, log_activity,
    add_balance, list_cards,
)
from db_products import (
    list_categories, list_products, get_product, create_order, get_order, update_order,
)
from services.provision import provision_order, send_service_to_user
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
        products = list_products(panel_id=panel_id, role=bu.get("role"), active_only=True)
        if not products:
            await q.edit_message_text("برای این پنل محصولی تعریف نشده.")
            return ConversationHandler.END
        cats = list_categories(active_only=True)
        cat_ids = {p.get("category_id") for p in products if p.get("category_id")}
        cats = [c for c in cats if c["id"] in cat_ids]
        if cats:
            rows = [[InlineKeyboardButton(c["name"], callback_data=f"buy_cat_{c['id']}")] for c in cats]
            rows.append([InlineKeyboardButton("همه محصولات", callback_data="buy_cat_0")])
            rows.append([InlineKeyboardButton("❌ انصراف", callback_data="buy_cancel")])
            text = render_template("buy_select_category", {}) or "📁 دسته را انتخاب کنید:"
            await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))
        else:
            await _show_products(q, context, panel_id, None, bu)
        return ConversationHandler.END

    if data.startswith("buy_cat_"):
        cat_id = int(data.replace("buy_cat_", ""))
        panel_id = context.user_data.get("buy_panel_id")
        await _show_products(q, context, panel_id, cat_id if cat_id else None, bu)
        return ConversationHandler.END

    if data.startswith("buy_prod_") or data.startswith("buy_full_") or data.startswith("buy_hour_"):
        is_hourly_buy = data.startswith("buy_hour_")
        is_full_buy = data.startswith("buy_full_")
        if is_hourly_buy:
            pid = int(data.replace("buy_hour_", ""))
        elif is_full_buy:
            pid = int(data.replace("buy_full_", ""))
        else:
            pid = int(data.replace("buy_prod_", ""))
        product = get_product(pid)
        panel_id = context.user_data.get("buy_panel_id")
        panel = get_panel_by_id(panel_id) if panel_id else None
        if not product or not panel:
            await q.edit_message_text("محصول نامعتبر.")
            return ConversationHandler.END

        # اگر محصول ساعتی مجاز است و هنوز نوع انتخاب نشده → انتخاب نوع خرید
        from database import get_setting_sync
        from datetime import datetime, timezone
        hourly_ok = (
            get_setting_sync("hourly_global_enabled", "0") == "1"
            and product.get("hourly_enabled")
            and product.get("hourly_price")
        )
        if hourly_ok and not is_hourly_buy and not is_full_buy:
            days = int(product.get("duration_days") or 30)
            hprice = float(product.get("hourly_price") or 0)
            full = int(product.get("price") or 0)
            await q.edit_message_text(
                f"📦 {product['name']}\n\n"
                f"نوع خرید را انتخاب کنید:\n"
                f"• کامل: {full:,} تومان / {days} روز\n"
                f"• ساعتی: {hprice:,.0f} تومان در ساعت\n"
                f"  (تقریبی روزانه: {hprice * 24:,.0f} تومان)",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛒 خرید کامل", callback_data=f"buy_full_{pid}")],
                    [InlineKeyboardButton("⏱ خرید ساعتی", callback_data=f"buy_hour_{pid}")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="buy_go")],
                ]),
            )
            return ConversationHandler.END

        if is_hourly_buy:
            # خرید ساعتی: فقط موجودی کیف پول — کسر اولین ساعت
            hprice = int(float(product.get("hourly_price") or 0))
            balance = int(bu.get("balance") or 0)
            if balance < hprice:
                await q.edit_message_text(
                    f"❌ موجودی کافی نیست.\nنیاز برای شروع: {hprice:,} تومان\nموجودی: {balance:,} تومان"
                )
                return ConversationHandler.END
            order_id = create_order(user.id, pid, panel_id, hprice, hprice, 0)
            add_balance(user.id, -hprice, f"hourly_start#{order_id}")
            update_order(
                order_id,
                status="paid",
                wallet_used=hprice,
                pay_amount=0,
                is_hourly=1,
                hourly_rate=hprice,
                hourly_active=1,
                hourly_started_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                hourly_last_charge_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            )
            await q.edit_message_text("⏱ در حال ساخت سرویس ساعتی...")
            result = provision_order(order_id)
            await send_service_to_user(context.bot, user.id, result)
            if result.get("ok"):
                await context.bot.send_message(
                    user.id,
                    f"✅ سرویس ساعتی فعال شد.\nهر ساعت {hprice:,} تومان از کیف پول کسر می‌شود.\n"
                    f"با دکمه «توقف سرویس ساعتی» می‌توانید قطع کنید.",
                )
            log_activity(user.id, "buy_hourly", str(order_id))
            return ConversationHandler.END

        price = int(product["price"] or 0)
        balance = int(bu.get("balance") or 0)
        wallet_used = min(balance, price)
        pay_amount = max(0, price - balance)
        order_id = create_order(user.id, pid, panel_id, price, wallet_used, pay_amount)

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
        text = render_template("buy_invoice", vars_) or (
            f"🧾 فاکتور\nمحصول: {product['name']}\nقیمت: {price:,}\nقابل پرداخت: {pay_amount:,}"
        )

        # موجودی کافی → کسر + ساخت فوری سرویس
        if pay_amount <= 0:
            add_balance(user.id, -wallet_used, f"order#{order_id}")
            update_order(order_id, status="paid", wallet_used=wallet_used, pay_amount=0)
            await q.edit_message_text(text + "\n\n⏳ در حال ساخت سرویس...")
            result = provision_order(order_id)
            await send_service_to_user(context.bot, user.id, result)
            try:
                from db_growth import pay_referral_commission
                pay_referral_commission(user.id, price)
            except Exception:
                pass
            if result.get("ok"):
                try:
                    await context.bot.send_message(
                        ADMIN_ID,
                        f"✅ سفارش #{order_id} تحویل شد (کیف پول)\nکاربر: {user.id}\n{product['name']}",
                    )
                except Exception:
                    pass
            else:
                await context.bot.send_message(
                    user.id,
                    f"پرداخت OK بود ولی ساخت سرویس خطا داد. با پشتیبانی تماس بگیرید.\n{result.get('error')}",
                )
            log_activity(user.id, "buy_instant", str(order_id))
            return ConversationHandler.END

        # کمبود موجودی → کارت به کارت + رسید + تایید ادمین
        rows = [
            [InlineKeyboardButton("💳 کارت به کارت", callback_data=f"buy_pay_card_{order_id}")],
            [InlineKeyboardButton("🏷 کد تخفیف", callback_data=f"buy_disc_{order_id}")],
            [InlineKeyboardButton("❌ انصراف", callback_data="buy_cancel")],
        ]
        context.user_data["buy_order_id"] = order_id
        context.user_data["buy_price"] = price
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))
        return ConversationHandler.END

    if data.startswith("buy_disc_"):
        oid = int(data.replace("buy_disc_", ""))
        context.user_data["buy_order_id"] = oid
        context.user_data["waiting_discount"] = True
        await q.edit_message_text("کد تخفیف را ارسال کنید:\n(یا /start انصراف)")
        return ConversationHandler.END

    if data.startswith("buy_pay_card_"):
        order_id = int(data.replace("buy_pay_card_", ""))
        order = get_order(order_id)
        if not order or order["telegram_id"] != user.id:
            await q.edit_message_text("سفارش نامعتبر.")
            return ConversationHandler.END
        cards = list_cards(active_only=True)
        if not cards:
            await q.edit_message_text("کارتی تعریف نشده. با پشتیبانی تماس بگیرید.")
            return ConversationHandler.END
        card = cards[0]
        update_order(order_id, method_key="card", card_id=card["id"], status="waiting_receipt")
        msg = (
            f"💳 مبلغ {int(order['pay_amount']):,} تومان را واریز کنید:\n\n"
            f"شماره کارت: `{card['card_number']}`\n"
            f"به نام: {card['owner_name']}\n\n"
            f"سپس تصویر رسید را ارسال کنید."
        )
        await q.edit_message_text(msg, parse_mode="Markdown")
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
        return
    rows = [[InlineKeyboardButton(
        f"{p['name']} — {int(p['price']):,} ت",
        callback_data=f"buy_prod_{p['id']}",
    )] for p in products]
    rows.append([InlineKeyboardButton("❌ انصراف", callback_data="buy_cancel")])
    text = render_template("buy_select_product", {}) or "📦 محصول را انتخاب کنید:"
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))

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
    await update.message.reply_text("⏳ رسید ثبت شد. پس از تایید ادمین سرویس برایتان ساخته می‌شود.")
    order = get_order(order_id)
    try:
        await context.bot.send_message(
            ADMIN_ID,
            f"🧾 رسید سفارش سرویس #{order_id}\nکاربر: {update.effective_user.id}\n"
            f"مبلغ قابل پرداخت: {int(order['pay_amount']):,} تومان\n"
            f"(موجودی کیف پول رزرو: {int(order.get('wallet_used') or 0):,})",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ تایید و ساخت سرویس", callback_data=f"adm_ord_ok_{order_id}"),
                InlineKeyboardButton("❌ رد", callback_data=f"adm_ord_no_{order_id}"),
            ]]),
        )
        await context.bot.send_photo(ADMIN_ID, file_id, caption=f"رسید سفارش #{order_id}")
    except Exception as e:
        print(e)
    context.user_data.pop("waiting_buy_receipt", None)
    return ConversationHandler.END
