# خرید سرویس جدید + تحویل خودکار

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import list_panels, get_panel_by_id, payment_method_button
from db_users import (
    get_bot_user, upsert_bot_user, render_template, log_activity,
    add_balance, list_cards, list_payment_methods,
)
from db_products import (
    list_categories, list_products, get_product, create_order, get_order, update_order,
    get_panel_price, batch_panel_prices,
)
from services.provision import provision_order, send_service_to_user
from config import ADMIN_ID

WAITING_BUY_RECEIPT = 20
WAITING_BUY_CUSTOM_NAME = 21

async def start_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_bot_user(user)
    panels = [p for p in (list_panels() or []) if p.get("is_active", 1)]
    if not panels:
        msg = "فعلاً پنلی برای خرید فعال نیست."
        if update.message:
            await update.message.reply_text(msg)
        else:
            await update.callback_query.edit_message_text(msg)
        return ConversationHandler.END
    from database import inline_button_from_entity
    rows = [[inline_button_from_entity(p, f"buy_panel_{p['id']}")] for p in panels]
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu_home")])
    text = render_template("buy_select_panel", {}) or "🖥 پنل مورد نظر را انتخاب کنید:"
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
    else:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
    log_activity(user.id, "buy_start")
    return ConversationHandler.END

async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    try:
        await q.answer()
    except Exception:
        pass
    data = q.data or ""
    user = update.effective_user
    try:
        bu = get_bot_user(user.id) or upsert_bot_user(user)
    except Exception as e:
        print("buy_callback get_bot_user:", e)
        bu = {}

    try:
        return await _buy_callback_inner(update, context, q, data, user, bu)
    except Exception as e:
        print(f"buy_callback error [{data}]: {e}")
        import traceback
        traceback.print_exc()
        try:
            await q.edit_message_text(f"❌ خطا در پردازش خرید.\n{type(e).__name__}: {e}")
        except Exception:
            try:
                await context.bot.send_message(user.id, f"❌ خطا در پردازش خرید.\n{e}")
            except Exception:
                pass
        return ConversationHandler.END


async def _buy_callback_inner(update, context, q, data, user, bu):
    if data == "buy_cancel":
        # سازگاری با callbackهای قدیمی — برگشت به منوی اصلی
        await q.edit_message_text(
            "به منوی اصلی برگشتید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_home")]]),
        )
        return ConversationHandler.END

    if data == "buy_go" or data == "buy_back_panel":
        return await start_buy(update, context)

    if data == "buy_back_cat":
        # برگشت به لیست دسته‌ها برای پنل فعلی
        panel_id = context.user_data.get("buy_panel_id")
        if not panel_id:
            return await start_buy(update, context)
        products = list_products(panel_id=panel_id, role=bu.get("role"), active_only=True)
        cats = list_categories(active_only=True)
        cat_ids = {p.get("category_id") for p in products if p.get("category_id")}
        cats = [c for c in cats if c["id"] in cat_ids]
        if cats:
            from database import inline_button_from_entity
            rows = [[inline_button_from_entity(c, f"buy_cat_{c['id']}")] for c in cats]
            rows.append([InlineKeyboardButton("همه محصولات", callback_data="buy_cat_0")])
            rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="buy_back_panel")])
            text = render_template("buy_select_category", {}) or "📁 دسته را انتخاب کنید:"
            await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
        else:
            return await start_buy(update, context)
        return ConversationHandler.END

    if data == "buy_back_prod":
        panel_id = context.user_data.get("buy_panel_id")
        cat_id = context.user_data.get("buy_cat_id")
        if not panel_id:
            return await start_buy(update, context)
        await _show_products(q, context, panel_id, cat_id, bu)
        return ConversationHandler.END

    if data.startswith("buy_panel_"):
        panel_id = int(data.replace("buy_panel_", ""))
        context.user_data["buy_panel_id"] = panel_id
        context.user_data.pop("buy_cat_id", None)
        products = list_products(panel_id=panel_id, role=bu.get("role"), active_only=True)
        if not products:
            await q.edit_message_text(
                "برای این پنل محصولی تعریف نشده.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="buy_back_panel")]]),
            )
            return ConversationHandler.END
        cats = list_categories(active_only=True)
        cat_ids = {p.get("category_id") for p in products if p.get("category_id")}
        cats = [c for c in cats if c["id"] in cat_ids]
        if cats:
            from database import inline_button_from_entity
            rows = [[inline_button_from_entity(c, f"buy_cat_{c['id']}")] for c in cats]
            rows.append([InlineKeyboardButton("همه محصولات", callback_data="buy_cat_0")])
            rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="buy_back_panel")])
            text = render_template("buy_select_category", {}) or "📁 دسته را انتخاب کنید:"
            await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
        else:
            await _show_products(q, context, panel_id, None, bu)
        return ConversationHandler.END

    if data.startswith("buy_cat_"):
        cat_id = int(data.replace("buy_cat_", ""))
        panel_id = context.user_data.get("buy_panel_id")
        context.user_data["buy_cat_id"] = cat_id if cat_id else None
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
            and (get_panel_price(product, panel_id, hourly=True) > 0 or float(product.get("hourly_price") or 0) > 0)
        )
        if hourly_ok and not is_hourly_buy and not is_full_buy:
            days = int(product.get("duration_days") or 30)
            hprice = float(get_panel_price(product, panel_id, hourly=True) if panel_id else (product.get("hourly_price") or 0))
            full = int(get_panel_price(product, panel_id, hourly=False) if panel_id else (product.get("price") or 0))
            await q.edit_message_text(
                f"📦 {product['name']}\n\n"
                f"نوع خرید را انتخاب کنید:\n"
                f"• کامل: {full:,} تومان / {days} روز\n"
                f"• ساعتی: {hprice:,.0f} تومان در ساعت\n"
                f"  (تقریبی روزانه: {hprice * 24:,.0f} تومان)",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🛒 خرید کامل", callback_data=f"buy_full_{pid}")],
                    [InlineKeyboardButton("⏱ خرید ساعتی", callback_data=f"buy_hour_{pid}")],
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="buy_back_prod")],
                ]),
            )
            return ConversationHandler.END

        # اگر محصول درخواست نام سفارشی دارد و هنوز نام گرفته نشده
        if product.get("ask_custom_name") and not context.user_data.get("buy_custom_name"):
            context.user_data["buy_pending_pid"] = pid
            context.user_data["buy_pending_hourly"] = 1 if is_hourly_buy else 0
            context.user_data["buy_panel_id"] = panel_id
            await q.edit_message_text(
                f"📦 {product['name']}\n\n"
                "✏️ نام سرویس مورد نظرتان را بنویسید:\n"
                "(این نام در پنل و بخش «سرویس‌های من» نمایش داده می‌شود)\n\n"
                "برای بازگشت دکمه زیر را بزنید یا /cancel بفرستید.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="buy_back_prod")],
                ]),
            )
            return WAITING_BUY_CUSTOM_NAME

        custom_name = (context.user_data.pop("buy_custom_name", None) or "").strip() or None

        if is_hourly_buy:
            # خرید ساعتی: فقط موجودی کیف پول — کسر اولین ساعت
            hprice = int(float(get_panel_price(product, panel_id, hourly=True) if panel_id else (product.get("hourly_price") or 0)))
            balance = int(bu.get("balance") or 0)
            if balance < hprice:
                await q.edit_message_text(
                    f"❌ موجودی کافی نیست.\nنیاز برای شروع: {hprice:,} تومان\nموجودی: {balance:,} تومان"
                )
                return ConversationHandler.END
            order_id = create_order(user.id, pid, panel_id, hprice, hprice, 0)
            if custom_name:
                update_order(order_id, custom_name=custom_name[:100])
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
                try:
                    from db_growth import award_purchase_points
                    award_purchase_points(user.id, hprice, order_id)
                except Exception as e:
                    print("hourly points:", e)
                await context.bot.send_message(
                    user.id,
                    f"✅ سرویس ساعتی فعال شد.\nهر ساعت {hprice:,} تومان از کیف پول کسر می‌شود.\n"
                    f"با دکمه «توقف سرویس ساعتی» می‌توانید قطع کنید.",
                )
            log_activity(user.id, "buy_hourly", str(order_id))
            return ConversationHandler.END


        # محدودیت فروش هر پنل
        try:
            max_s = panel.get("max_sales")
            if max_s is not None and int(max_s) > 0:
                from database import get_sync_connection
                conn = get_sync_connection()
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COUNT(*) AS c FROM service_orders WHERE panel_id=%s AND status IN ('paid','provisioned')",
                        (panel_id,),
                    )
                    cnt = int((cur.fetchone() or {}).get("c") or 0)
                conn.close()
                if cnt >= int(max_s):
                    await q.edit_message_text("❌ ظرفیت فروش این پنل تکمیل شده است.")
                    return ConversationHandler.END
        except Exception as e:
            print("max_sales check", e)

        price = int(get_panel_price(product, panel_id, hourly=False) if panel_id else (product.get("price") or 0))
        balance = int(bu.get("balance") or 0)
        wallet_used = min(balance, price)
        pay_amount = max(0, price - balance)
        order_id = create_order(user.id, pid, panel_id, price, wallet_used, pay_amount)
        if custom_name:
            update_order(order_id, custom_name=custom_name[:100])

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

        # موجودی کافی → اول تایید کاربر، بعد کسر و ساخت
        if pay_amount <= 0:
            context.user_data["buy_order_id"] = order_id
            context.user_data["buy_price"] = price
            rows = [
                [InlineKeyboardButton("✅ تایید و پرداخت از کیف پول", callback_data=f"buy_confirm_{order_id}")],
                [InlineKeyboardButton("🏷 کد تخفیف", callback_data=f"buy_disc_{order_id}")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="buy_back_prod")],
            ]
            await q.edit_message_text(
                text + "\n\n⚠️ با تایید، مبلغ از کیف پول کسر و سرویس ساخته می‌شود.",
                reply_markup=InlineKeyboardMarkup(rows),
            )
            return ConversationHandler.END

        # کمبود موجودی → روش‌های پرداخت فعال (با پشتیبانی ایموجی پریمیوم در عنوان)
        rows = []
        from database import get_setting_sync
        from db_users import user_can_see_card
        for pm in list_payment_methods(active_only=True):
            key = pm.get("method_key")
            if key == "variza":
                try:
                    from services.variza import is_enabled, configured
                    if not (is_enabled() and configured()):
                        continue
                except Exception:
                    continue
            if key == "card":
                if not list_cards(active_only=True):
                    continue
                if not user_can_see_card(user.id):
                    continue
            if key == "stars":
                if get_setting_sync("stars_enabled", "0") != "1":
                    continue
            rows.append([payment_method_button(pm, f"buy_pay_{key}_{order_id}")])
        rows.extend([
            [InlineKeyboardButton("🏷 کد تخفیف", callback_data=f"buy_disc_{order_id}")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="buy_back_prod")],
        ])
        context.user_data["buy_order_id"] = order_id
        context.user_data["buy_price"] = price
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
        return ConversationHandler.END


    if data.startswith("buy_confirm_"):
        oid = int(data.replace("buy_confirm_", ""))
        order = get_order(oid)
        if not order or order["telegram_id"] != user.id:
            await q.edit_message_text("سفارش نامعتبر.")
            return ConversationHandler.END
        product = get_product(order["product_id"])
        price = int(order.get("amount") or 0)
        bu2 = get_bot_user(user.id) or {}
        balance = int(bu2.get("balance") or 0)
        if balance < price:
            await q.edit_message_text(f"❌ موجودی کافی نیست.\nموجودی: {balance:,} / لازم: {price:,}")
            return ConversationHandler.END
        add_balance(user.id, -price, f"order#{oid}")
        update_order(oid, status="paid", wallet_used=price, pay_amount=0)
        await q.edit_message_text("⏳ در حال ساخت سرویس...")
        result = provision_order(oid)
        await send_service_to_user(context.bot, user.id, result)
        if result.get("ok"):
            try:
                from db_growth import award_purchase_points
                award_purchase_points(user.id, price, oid)
            except Exception as e:
                print("purchase points:", e)
        try:
            from db_growth import pay_referral_commission
            pay_referral_commission(user.id, price)
        except Exception:
            pass
        if result.get("ok"):
            try:
                await context.bot.send_message(ADMIN_ID, f"✅ سفارش #{oid} تحویل شد (کیف پول)\nکاربر: {user.id}")
            except Exception:
                pass
        else:
            await context.bot.send_message(user.id, f"ساخت سرویس خطا داد.\n{result.get('error')}")
        log_activity(user.id, "buy_confirmed", str(oid))
        return ConversationHandler.END

    if data.startswith("buy_disc_"):
        oid = int(data.replace("buy_disc_", ""))
        context.user_data["buy_order_id"] = oid
        context.user_data["waiting_discount"] = True
        await q.edit_message_text(
            "کد تخفیف را ارسال کنید:\n(یا /cancel برای بازگشت)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="buy_back_prod")]]),
        )
        return ConversationHandler.END

    if data.startswith("buy_pay_variza_"):
        order_id = int(data.replace("buy_pay_variza_", ""))
        order = get_order(order_id)
        if not order or order["telegram_id"] != user.id:
            await q.edit_message_text("سفارش نامعتبر.")
            return ConversationHandler.END
        try:
            from services.variza import create_payment_link, save_order_link
            pay_amount = int(order.get("pay_amount") or 0)
            data_v = create_payment_link(pay_amount, "order", order_id, f"خرید سرویس #{order_id}")
            save_order_link(order_id, data_v)
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("💳 پرداخت با واریزا", url=data_v["pay_url"])],
                                       [InlineKeyboardButton("🔙 بازگشت", callback_data="buy_back_prod")],
                                       [InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_home")]])
            await q.edit_message_text(
                f"🧾 سفارش #{order_id}\n\nمبلغ قابل پرداخت: <b>{pay_amount:,}</b> تومان\n\n"
                "با دکمه زیر وارد واریزا شوید. بعد از پرداخت، سفارش به‌صورت خودکار تایید و سرویس ساخته می‌شود؛ رسید لازم نیست.\n\n"
                "⚠️ مبلغ نهایی ممکن است برای تطبیق بانکی کمی متفاوت باشد و بر اساس شناسه پرداخت تطبیق می‌شود.",
                reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            await q.edit_message_text(f"❌ ساخت لینک واریزا ناموفق بود.\n{str(e)[:250]}")
        return ConversationHandler.END

    if data.startswith("buy_pay_card_"):
        order_id = int(data.replace("buy_pay_card_", ""))
        order = get_order(order_id)
        if not order or order["telegram_id"] != user.id:
            await q.edit_message_text("سفارش نامعتبر.")
            return ConversationHandler.END
        from db_users import user_can_see_card
        if not user_can_see_card(user.id):
            await q.edit_message_text(
                "💳 پرداخت کارت‌به‌کارت پس از اولین خرید موفق در دسترس است.\n"
                "لطفاً از روش‌های دیگر یا شارژ کیف پول استفاده کنید."
            )
            return ConversationHandler.END
        cards = list_cards(active_only=True)
        if not cards:
            await q.edit_message_text("کارتی تعریف نشده. با پشتیبانی تماس بگیرید.")
            return ConversationHandler.END
        card = cards[0]
        update_order(order_id, method_key="card", card_id=card["id"], status="waiting_receipt")
        card_num = str(card["card_number"]).replace(" ", "").replace("-", "")
        owner = (card.get("owner_name") or "").strip()
        # استفاده از HTML به‌جای Markdown تا نام صاحب کارت یا اعداد باعث خطای parse نشود
        msg = (
            f"💳 مبلغ <b>{int(order['pay_amount']):,}</b> تومان را واریز کنید:\n\n"
            f"شماره کارت: <code>{card_num}</code>\n"
            f"به نام: {owner}\n\n"
            f"سپس تصویر رسید را ارسال کنید."
        )
        try:
            from telegram import CopyTextButton
            copy_btn = InlineKeyboardButton("📋 کپی شماره کارت", copy_text=CopyTextButton(text=card_num))
        except Exception:
            copy_btn = InlineKeyboardButton("📋 کپی شماره کارت", callback_data=f"copy_card_{card['id']}")
        kb = InlineKeyboardMarkup([
            [copy_btn],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="buy_back_prod")],
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_home")],
        ])
        try:
            await q.edit_message_text(msg, parse_mode="HTML", reply_markup=kb)
        except Exception:
            # اگر ادیت پیام قبلی شکست خورد، پیام جدید بفرست
            await context.bot.send_message(user.id, msg, parse_mode="HTML", reply_markup=kb)
        context.user_data["waiting_buy_receipt"] = order_id
        return WAITING_BUY_RECEIPT


    if data.startswith("buy_pay_stars_"):
        order_id = int(data.replace("buy_pay_stars_", ""))
        order = get_order(order_id)
        if not order or order["telegram_id"] != user.id:
            await q.edit_message_text("سفارش نامعتبر.")
            return ConversationHandler.END
        from database import get_setting_sync
        if get_setting_sync("stars_enabled", "0") != "1":
            await q.edit_message_text("پرداخت با استارز غیرفعال است.")
            return ConversationHandler.END
        pay_amount = int(order.get("pay_amount") or 0)
        try:
            rate = float(get_setting_sync("stars_rate", "1000") or 1000)
        except Exception:
            rate = 1000.0
        if rate <= 0:
            rate = 1000.0
        stars_amount = max(1, int(round(pay_amount / rate)))
        title = get_setting_sync("stars_payment_title", "⭐ استارز تلگرام") or "⭐ استارز تلگرام"
        try:
            from telegram import LabeledPrice
            await context.bot.send_invoice(
                chat_id=user.id,
                title=title[:32],
                description=f"خرید سرویس #{order_id} — {pay_amount:,} تومان",
                payload=f"order_stars_{order_id}",
                provider_token="",
                currency="XTR",
                prices=[LabeledPrice(label=title[:32], amount=stars_amount)],
            )
            update_order(order_id, method_key="stars", status="pending_payment")
            await q.edit_message_text(
                f"⭐ فاکتور استارز ارسال شد.\n"
                f"مبلغ: <b>{pay_amount:,}</b> تومان ≈ <b>{stars_amount}</b> استار\n"
                f"نرخ: هر استار ≈ {int(rate):,} تومان",
                parse_mode="HTML",
            )
        except Exception as e:
            await q.edit_message_text(f"❌ خطا در ساخت فاکتور استارز:\n{str(e)[:250]}")
        return ConversationHandler.END

    return ConversationHandler.END


async def _show_products(q, context, panel_id, cat_id, bu):
    products = list_products(
        category_id=cat_id if cat_id else None,
        panel_id=panel_id,
        role=bu.get("role"),
        active_only=True,
        with_panels=False,
    )
    if not products:
        await q.edit_message_text("محصولی در این دسته نیست.")
        return
    price_map = {}
    if panel_id:
        try:
            price_map = batch_panel_prices([p["id"] for p in products], int(panel_id)) or {}
        except Exception as e:
            print("show_products panel prices:", e)
    rows = []
    for p in products:
        pid = int(p["id"])
        price = int(price_map.get(pid, p.get("price") or 0))
        rows.append([InlineKeyboardButton(
            f"{p['name']} — {price:,} ت",
            callback_data=f"buy_prod_{pid}",
        )])
    # برگشت: اگر دسته انتخاب شده بود → لیست دسته؛ وگرنه → لیست پنل
    back_cb = "buy_back_cat" if context.user_data.get("buy_cat_id") is not None or context.user_data.get("buy_had_cats") else "buy_back_panel"
    # تشخیص دسته‌دار بودن پنل
    try:
        prods_all = list_products(panel_id=panel_id, role=bu.get("role"), active_only=True, with_panels=False) or []
        has_cats = any(p.get("category_id") for p in prods_all)
        if has_cats:
            back_cb = "buy_back_cat"
            context.user_data["buy_had_cats"] = True
        else:
            back_cb = "buy_back_panel"
            context.user_data["buy_had_cats"] = False
    except Exception:
        pass
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data=back_cb)])
    text = render_template("buy_select_product", {}) or "📦 محصول را انتخاب کنید:"
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")

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
    user = update.effective_user
    try:
        from db_users import get_bot_user
        bu = get_bot_user(user.id) or {}
        display_name = " ".join(filter(None, [user.first_name, user.last_name])) or bu.get("first_name") or "—"
        username_str = f"@{user.username}" if user.username else (bu.get("username") and f"@{bu.get('username')}") or "—"
        phone_str = bu.get("phone") or "—"
        await context.bot.send_message(
            ADMIN_ID,
            (
                f"🧾 رسید سفارش سرویس #{order_id}\n"
                f"کاربر: <code>{user.id}</code>\n"
                f"نام: {display_name}\n"
                f"یوزرنیم: {username_str}\n"
                f"شماره: {phone_str}\n"
                f"مبلغ قابل پرداخت: {int(order['pay_amount']):,} تومان\n"
                f"(موجودی کیف پول رزرو: {int(order.get('wallet_used') or 0):,})"
            ),
            parse_mode="HTML",
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


async def receive_buy_custom_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت نام سفارشی سرویس هنگام خرید (قبل از فاکتور)."""
    user = update.effective_user
    name = (update.message.text or "").strip()
    if name.lower() in ("/cancel", "cancel", "انصراف", "/start"):
        context.user_data.pop("buy_pending_pid", None)
        context.user_data.pop("buy_pending_hourly", None)
        context.user_data.pop("buy_custom_name", None)
        await update.message.reply_text(
            "بازگشت.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به محصولات", callback_data="buy_back_prod")]]),
        )
        return ConversationHandler.END
    if not name or len(name) < 2:
        await update.message.reply_text("نام سرویس حداقل ۲ کاراکتر باشد. دوباره بفرستید:\n(/cancel برای بازگشت)")
        return WAITING_BUY_CUSTOM_NAME
    if len(name) > 100:
        name = name[:100]
    pid = context.user_data.get("buy_pending_pid")
    is_hourly = context.user_data.get("buy_pending_hourly")
    panel_id = context.user_data.get("buy_panel_id")
    if not pid:
        await update.message.reply_text("نشست خرید منقضی شده. دوباره از منوی خرید شروع کنید.")
        return ConversationHandler.END
    context.user_data["buy_custom_name"] = name
    context.user_data.pop("buy_pending_pid", None)
    context.user_data.pop("buy_pending_hourly", None)
    # ادامهٔ جریان خرید با همان callback داخلی
    class _FakeQuery:
        def __init__(self, message):
            self.message = message
            self.data = f"buy_hour_{pid}" if is_hourly else f"buy_full_{pid}"
            self.from_user = user
        async def edit_message_text(self, *a, **k):
            return await update.message.reply_text(a[0] if a else k.get("text", ""), reply_markup=k.get("reply_markup"))
        async def answer(self, *a, **k):
            return None
    bu = get_bot_user(user.id)
    fake_q = _FakeQuery(update.message)
    data = f"buy_hour_{pid}" if is_hourly else f"buy_full_{pid}"
    return await _buy_callback_inner(update, context, fake_q, data, user, bu)
