# سرویس‌های من + پشتیبانی ساده + آموزش

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID
from db_users import get_template, log_activity, upsert_bot_user, get_bot_user, add_balance
from db_support import (
    list_user_orders, get_user_order, list_departments, create_ticket,
    add_ticket_message, list_user_tickets, get_ticket, get_ticket_messages, close_ticket,
)
from db_products import get_product
from services.pasarguard import PasarGuardClient
from services.panel_client import get_panel_client, is_xui_panel
from services.provision import fix_subscription_url, make_qr_png
from database import get_setting_sync
import io
from datetime import datetime, timedelta, timezone

WAITING_TICKET_MSG = 31
WAITING_RENAME = 32

def _panel_creds(o: dict):
    base = o.get("base_url") or o.get("panel_base") or ""
    user = o.get("panel_user") or o.get("username")
    # password field from join
    pwd = o.get("panel_pass") or o.get("password")
    return base, user, pwd

def _client(o: dict):
    """کلاینت پنل بر اساس نوع (پاسارگارد / 3x-ui)"""
    base = o.get("base_url") or o.get("panel_base") or ""
    user = o.get("panel_user") or o.get("username") or ""
    pwd = o.get("panel_pass") or o.get("password") or ""
    api_key = o.get("api_key") or ""
    ptype = o.get("panel_type") or "pasarguard"
    if not base:
        # fallback: load panel by id
        try:
            from database import get_panel_by_id
            panel = get_panel_by_id(o.get("panel_id")) if o.get("panel_id") else None
            if panel:
                return get_panel_client(panel)
        except Exception:
            pass
        raise RuntimeError("اطلاعات پنل ناقص است")
    panel = {
        "base_url": base,
        "username": user,
        "password": pwd,
        "api_key": api_key,
        "panel_type": ptype,
    }
    # اگر api_key/type در سفارش نبود از DB بگیر
    if o.get("panel_id") and (not api_key or ptype == "pasarguard"):
        try:
            from database import get_panel_by_id
            full = get_panel_by_id(o["panel_id"])
            if full:
                panel = full
        except Exception:
            pass
    return get_panel_client(panel)

def back_main_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="svc_list")]])

def service_card_keyboard(order_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 بروزرسانی", callback_data=f"svc_refresh_{order_id}"),
            InlineKeyboardButton("♻️ تمدید سرویس", callback_data=f"svc_renewmenu_{order_id}"),
        ],
        [
            InlineKeyboardButton("🔐 بازنشانی اشتراک", callback_data=f"svc_reset_{order_id}"),
            InlineKeyboardButton("⏯ خاموش / روشن", callback_data=f"svc_toggle_{order_id}"),
        ],
        [
            InlineKeyboardButton("📎 لینک و QR", callback_data=f"svc_link_{order_id}"),
            InlineKeyboardButton("🌍 تغییر لوکیشن", callback_data=f"svc_loc_{order_id}"),
        ],
        [
            InlineKeyboardButton("✏️ تغییر نام", callback_data=f"svc_rename_{order_id}"),
            InlineKeyboardButton("⚠️ گزارش اختلال", callback_data=f"svc_report_{order_id}"),
        ],
        [
            InlineKeyboardButton("💸 بازگشت وجه", callback_data=f"svc_refund_{order_id}"),
            InlineKeyboardButton("⏯ ساعتی", callback_data=f"svc_htoggle_{order_id}"),
        ],
        [InlineKeyboardButton("🔙 لیست سرویس‌ها", callback_data="svc_list")],
        [InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_home")],
    ])


def _remaining_days(expire_val) -> str:
    """محاسبه روز باقی‌مانده از فیلد expire پنل — نامحدود یا عدد روز"""
    if expire_val is None or expire_val == "" or expire_val == 0 or expire_val == "0":
        return "∞"
    try:
        if isinstance(expire_val, (int, float)):
            ts = int(expire_val)
            if ts > 1e12:  # milliseconds
                ts = ts // 1000
            exp_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        else:
            s = str(expire_val).strip().replace("Z", "+00:00")
            exp_dt = datetime.fromisoformat(s)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = exp_dt - now
        days = max(0, delta.days)
        return str(days)
    except Exception:
        return "—"


def build_service_status_text(o: dict) -> str:
    """
    ساخت متن وضعیت سرویس با داده‌های زنده از پاسارگارد
    مطابق قالب درخواستی کاربر.
    """
    volume_plan = o.get("volume_gb") or "—"
    days_plan = o.get("duration_days") or "—"
    channel = get_setting_sync("channel_id", "") or get_setting_sync("support_channel", "") or "—"

    # fallback بدون اتصال پنل
    text = (
        f"📦 سرویس {volume_plan} گیگابایت - {days_plan} روز\n"
        f"📊 وضعیت: {o.get('status') or '—'}\n"
        f"📱 تعداد دستگاه‌های متصل به این سرویس: —\n"
        f"🔢 شماره سرویس: {o.get('id')}\n"
        f"⏳ زمان باقی‌مانده: — روز\n"
        f"💾 حجم باقی‌مانده: — گیگابایت\n"
        f"🔗 لینک اتصال:\n—\n"
        f"ℹ️ توجه: آموزش اتصال به سرویس‌ها را می‌توانید در بخش «مرکز آموزش» ببینید.\n"
        f"🔐 برای تغییر رمز و قطع دسترسی افراد متصل به پروکسی روی دکمه زیر کلیک کنید\n"
        f"{channel}"
    )

    if not o.get("vpn_username"):
        return text

    try:
        client = _client(o)
        full = client.get_user(o["vpn_username"]) or {}
        raw = full.get("subscription_url") or full.get("subscription_link") or ""
        if not raw and full.get("subscription_token"):
            raw = f"/sub/{full['subscription_token']}"
        if not raw and full.get("subId") and hasattr(client, "subscription_url"):
            try:
                raw = client.subscription_url(full.get("subId"), email=o["vpn_username"])
            except Exception:
                raw = ""
        base = o.get("base_url") or o.get("panel_base") or ""
        if not base:
            try:
                base, _, _ = _panel_creds(o)
            except Exception:
                base = ""
        link = raw if (raw or "").startswith("http") else fix_subscription_url(base, raw)

        st = full.get("status") or "—"
        hwid = full.get("hwid_limit")
        if hwid is None:
            hwid = full.get("limitIp")
        if hwid is None or hwid == 0 or hwid == "0":
            hwid = "نامحدود"

        used = full.get("used_traffic") or 0
        limit = full.get("data_limit") or 0
        remain_gb = "∞"
        if limit and int(limit) > 0:
            remain_gb = round(max(0, (int(limit) - int(used)) / (1024 ** 3)), 2)

        remain_days = _remaining_days(full.get("expire"))

        vol_show = remain_gb if remain_gb != "∞" else (volume_plan if volume_plan != "—" else "∞")
        days_show = remain_days if remain_days != "∞" else (days_plan if days_plan != "—" else "∞")

        text = (
            f"📦 سرویس {vol_show} گیگابایت - {days_show} روز\n"
            f"📊 وضعیت: {st}\n"
            f"📱 تعداد دستگاه‌های متصل به این سرویس: {hwid}\n"
            f"🔢 شماره سرویس: {o.get('id')}\n"
            f"⏳ زمان باقی‌مانده: {remain_days} روز\n"
            f"💾 حجم باقی‌مانده: {remain_gb} گیگابایت\n"
            f"🔗 لینک اتصال:\n{link or '—'}\n"
            f"ℹ️ توجه: آموزش اتصال به سرویس‌ها را می‌توانید در بخش «مرکز آموزش» ببینید.\n"
            f"🔐 برای تغییر رمز و قطع دسترسی افراد متصل به پروکسی روی دکمه زیر کلیک کنید\n"
            f"{channel}"
        )
    except Exception as e:
        text += f"\n\n⚠️ دریافت وضعیت زنده: {e}"

    return text

async def show_my_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_bot_user(user)
    orders = list_user_orders(user.id)
    if not orders:
        text = "هنوز سرویسی ندارید.\nاز «خرید سرویس جدید» یک سرویس بگیرید."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛒 خرید سرویس", callback_data="buy_go")]])
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text, reply_markup=kb)
        else:
            await update.message.reply_text(text, reply_markup=kb)
        return
    rows = []
    for o in orders:
        product = o.get("product_name") or "محصول"
        uname = o.get("vpn_username") or f"#{o['id']}"
        cname = (o.get("custom_name") or "").strip()
        label = f"{cname} ({uname})" if cname else f"{uname} - {product}"
        rows.append([InlineKeyboardButton(label[:60], callback_data=f"svc_open_{o['id']}")])
    rows.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_home")])
    text = "📱 سرویس‌های من\nسرویس خریداری‌شده را انتخاب کنید:"
    kb = InlineKeyboardMarkup(rows)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)
    log_activity(user.id, "my_services")

async def services_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    user = update.effective_user

    if data == "buy_go":
        from handlers.buy import start_buy
        return await start_buy(update, context)

    if data == "svc_list":
        await show_my_services(update, context)
        return ConversationHandler.END

    if data.startswith("svc_open_") or data.startswith("svc_refresh_"):
        oid = int(data.split("_")[-1])
        o = get_user_order(oid, user.id)
        if not o:
            await q.edit_message_text("سرویس پیدا نشد.", reply_markup=back_main_kb())
            return ConversationHandler.END
        text = build_service_status_text(o)
        kb = service_card_keyboard(oid)
        try:
            await q.edit_message_text(text, reply_markup=kb)
        except Exception:
            pass  # متن یکسان → تلگرام خطا می‌دهد؛ مشکلی نیست
        return ConversationHandler.END

    # ---- actions need order ----
    def _oid(prefix):
        return int(data.replace(prefix, ""))

    if data.startswith("svc_link_"):
        oid = _oid("svc_link_")
        o = get_user_order(oid, user.id)
        if not o or not o.get("vpn_username"):
            await q.edit_message_text("اکانت متصل نیست.", reply_markup=service_card_keyboard(oid) if o else back_main_kb())
            return ConversationHandler.END
        try:
            client = _client(o)
            full = client.get_user(o["vpn_username"])
            raw = full.get("subscription_url") or full.get("subscription_link") or ""
            if not raw and full.get("subscription_token"):
                raw = f"/sub/{full['subscription_token']}"
            base, _, _ = _panel_creds(o)
            link = fix_subscription_url(base, raw)
            if not link:
                await q.edit_message_text("لینک یافت نشد.", reply_markup=service_card_keyboard(oid))
                return ConversationHandler.END
            qr = make_qr_png(link)
            caption = f"لینک اتصال:\n{link}"
            if qr:
                await context.bot.send_photo(user.id, photo=InputFile(io.BytesIO(qr), filename="qr.png"), caption=caption[:1000])
                await q.edit_message_text("✅ لینک و QR ارسال شد.", reply_markup=service_card_keyboard(oid))
            else:
                await q.edit_message_text(caption, reply_markup=service_card_keyboard(oid))
        except Exception as e:
            await q.edit_message_text(f"❌ خطا: {e}", reply_markup=service_card_keyboard(oid))
        return ConversationHandler.END

    if data.startswith("svc_reset_"):
        oid = _oid("svc_reset_")
        o = get_user_order(oid, user.id)
        if not o or not o.get("vpn_username"):
            await q.edit_message_text("اکانت نیست.", reply_markup=back_main_kb())
            return ConversationHandler.END
        try:
            client = _client(o)
            uname = o["vpn_username"]
            try:
                client._request("POST", f"/api/user/{uname}/revoke")
            except Exception:
                client._request("POST", f"/api/user/{uname}/revoke_sub")
            await q.edit_message_text(
                "✅ اشتراک بازنشانی شد.\nلینک قبلی از کار می‌افتد — از «لینک و QR» لینک جدید بگیرید.",
                reply_markup=service_card_keyboard(oid),
            )
        except Exception as e:
            await q.edit_message_text(f"❌ خطا در بازنشانی: {e}", reply_markup=service_card_keyboard(oid))
        return ConversationHandler.END

    if data.startswith("svc_toggle_"):
        oid = _oid("svc_toggle_")
        o = get_user_order(oid, user.id)
        if not o or not o.get("vpn_username"):
            await q.edit_message_text("اکانت نیست.", reply_markup=back_main_kb())
            return ConversationHandler.END
        try:
            client = _client(o)
            uname = o["vpn_username"]
            full = client.get_user(uname)
            st = (full.get("status") or "active").lower()
            make_disabled = st in ("active", "on_hold")
            try:
                client._request("PUT", f"/api/user/{uname}/disabled", json={"disabled": make_disabled})
            except Exception:
                client.modify_user(uname, {"status": "disabled" if make_disabled else "active"})
            label = "خاموش (disabled)" if make_disabled else "روشن (active)"
            await q.edit_message_text(f"✅ سرویس اکنون {label} است.", reply_markup=service_card_keyboard(oid))
        except Exception as e:
            await q.edit_message_text(f"❌ خطا: {e}", reply_markup=service_card_keyboard(oid))
        return ConversationHandler.END

    # ---- منوی تمدید: لیست پلن‌های همان پنل ----
    if data.startswith("svc_renewmenu_"):
        oid = int(data.replace("svc_renewmenu_", ""))
        o = get_user_order(oid, user.id)
        if not o or not o.get("vpn_username"):
            await q.edit_message_text("اکانت نیست.", reply_markup=back_main_kb())
            return ConversationHandler.END
        panel_id = o.get("panel_id")
        from db_products import list_products
        bu = get_bot_user(user.id) or {}
        products = list_products(panel_id=panel_id, role=bu.get("role"), active_only=True) if panel_id else []
        if not products:
            products = list_products(active_only=True, role=bu.get("role"))
        if not products:
            await q.edit_message_text("پلنی برای تمدید تعریف نشده.", reply_markup=service_card_keyboard(oid))
            return ConversationHandler.END
        rows = []
        for pr in products:
            label = f"{pr['name']} — {int(pr.get('price') or 0):,} ت / {pr.get('volume_gb')}GB / {pr.get('duration_days')}روز"
            rows.append([InlineKeyboardButton(label[:60], callback_data=f"svc_plan_{oid}_{pr['id']}")])
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"svc_open_{oid}")])
        await q.edit_message_text(
            "♻️ پلن تمدید را انتخاب کنید:\n(بر اساس تنظیم روش تمدید پنل اعمال می‌شود)",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return ConversationHandler.END

    if data.startswith("svc_plan_"):
        # svc_plan_{orderId}_{productId}
        parts = data.replace("svc_plan_", "").split("_")
        oid, pid = int(parts[0]), int(parts[1])
        o = get_user_order(oid, user.id)
        product = get_product(pid)
        if not o or not product or not o.get("vpn_username"):
            await q.edit_message_text("نامعتبر.", reply_markup=back_main_kb())
            return ConversationHandler.END
        price = int(product.get("price") or 0)
        days = int(product.get("duration_days") or 30)
        volume = float(product.get("volume_gb") or 0)
        bu = get_bot_user(user.id)
        balance = int((bu or {}).get("balance") or 0)
        if price > balance:
            await q.edit_message_text(f"موجودی کم است. نیاز: {price:,}", reply_markup=service_card_keyboard(oid))
            return ConversationHandler.END
        # روش تمدید از پنل
        renew_mode = "reset_both"
        try:
            from database import get_panel_by_id
            panel = get_panel_by_id(o.get("panel_id")) if o.get("panel_id") else None
            if panel and panel.get("renew_mode"):
                renew_mode = panel["renew_mode"]
        except Exception:
            pass
        try:
            if price > 0:
                add_balance(user.id, -price, f"renew_plan#{oid}")
            client = _client(o)
            uname = o["vpn_username"]
            full = {}
            try:
                full = client.get_user(uname) or {}
            except Exception:
                full = {}
            now = datetime.now(timezone.utc)
            payload = {"status": "active"}
            # زمان
            if renew_mode in ("reset_both", "reset_time"):
                new_exp = (now + timedelta(days=days)).isoformat()
                payload["expire"] = new_exp
            elif renew_mode in ("additive",):
                exp = full.get("expire")
                base_dt = now
                if exp:
                    try:
                        if isinstance(exp, (int, float)) and exp > 0:
                            ts = int(exp)
                            if ts > 1e12:
                                ts = ts // 1000
                            base_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                        else:
                            base_dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
                        if base_dt.tzinfo is None:
                            base_dt = base_dt.replace(tzinfo=timezone.utc)
                        if base_dt < now:
                            base_dt = now
                    except Exception:
                        base_dt = now
                payload["expire"] = (base_dt + timedelta(days=days)).isoformat()
            # حجم
            if renew_mode in ("reset_both", "reset_volume"):
                if volume > 0:
                    payload["data_limit"] = int(volume * 1024 ** 3)
                else:
                    payload["data_limit"] = 0
            elif renew_mode == "additive" and volume > 0:
                current_limit = float(full.get("data_limit") or 0)
                payload["data_limit"] = int(current_limit + volume * 1024 ** 3)
            # ریست مصرف در حالت‌های ریست حجم/هر دو
            if renew_mode in ("reset_both", "reset_volume"):
                try:
                    client._request("POST", f"/api/user/{uname}/reset")
                except Exception:
                    pass
            client.modify_user(uname, payload)
            mode_labels = {
                "reset_both": "ریست زمان و حجم",
                "reset_time": "ریست زمان فقط",
                "reset_volume": "ریست حجم فقط",
                "additive": "افزایشی (بدون ریست)",
            }
            await q.edit_message_text(
                f"✅ تمدید با پلن «{product['name']}» انجام شد.\n"
                f"{days} روز / {volume} GB / {price:,} تومان\n"
                f"روش: {mode_labels.get(renew_mode, renew_mode)}",
                reply_markup=service_card_keyboard(oid),
            )
            log_activity(user.id, "renew_plan", f"{oid}:{pid}")
        except Exception as e:
            if price > 0:
                try:
                    add_balance(user.id, price, f"renew_plan_refund#{oid}")
                except Exception:
                    pass
            await q.edit_message_text(f"❌ {e}", reply_markup=service_card_keyboard(oid))
        return ConversationHandler.END

    # سازگاری با callback قدیمی → منوی تمدید
    if data.startswith("svc_renew_") and not data.startswith("svc_renewmenu_"):
        oid = _oid("svc_renew_")
        # همان منطق منوی تمدید
        o = get_user_order(oid, user.id)
        if not o or not o.get("vpn_username"):
            await q.edit_message_text("اکانت نیست.", reply_markup=back_main_kb())
            return ConversationHandler.END
        panel_id = o.get("panel_id")
        from db_products import list_products
        bu = get_bot_user(user.id) or {}
        products = list_products(panel_id=panel_id, role=bu.get("role"), active_only=True) if panel_id else []
        if not products:
            products = list_products(active_only=True, role=bu.get("role"))
        rows = []
        for pr in products:
            label = f"{pr['name']} — {int(pr.get('price') or 0):,} ت / {pr.get('volume_gb')}GB / {pr.get('duration_days')}روز"
            rows.append([InlineKeyboardButton(label[:60], callback_data=f"svc_plan_{oid}_{pr['id']}")])
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"svc_open_{oid}")])
        await q.edit_message_text(
            "♻️ پلن تمدید را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return ConversationHandler.END

    # ---- تغییر نام سرویس ----
    if data.startswith("svc_rename_"):
        oid = int(data.replace("svc_rename_", ""))
        o = get_user_order(oid, user.id)
        if not o:
            await q.edit_message_text("سرویس پیدا نشد.", reply_markup=back_main_kb())
            return ConversationHandler.END
        context.user_data["rename_order_id"] = oid
        await q.edit_message_text(
            "✏️ نام دلخواه سرویس را بفرستید.\n"
            "نام نباید تکراری باشد.\n\n"
            "/cancel برای انصراف · /skip برای حذف نام سفارشی",
        )
        return WAITING_RENAME


    # ---- توقف سرویس ساعتی ----
    if data.startswith("svc_htoggle_"):
        oid = int(data.replace("svc_htoggle_", ""))
        from db_products import get_order_full, update_order
        from services.service_edit import _client_from_order
        o = get_order_full(oid)
        if not o or o.get("telegram_id") != user.id:
            await q.edit_message_text("سرویس نامعتبر.", reply_markup=back_main_kb())
            return ConversationHandler.END
        if not o.get("is_hourly"):
            await q.edit_message_text("این سرویس ساعتی نیست.", reply_markup=service_card_keyboard(oid))
            return ConversationHandler.END
        active = int(o.get("hourly_active") or 0)
        new_active = 0 if active else 1
        try:
            if o.get("vpn_username"):
                client = _client_from_order(o)
                client.modify_user(o["vpn_username"], {"status": "active" if new_active else "disabled"})
            update_order(oid, hourly_active=new_active)
            msg = "🟢 سرویس ساعتی روشن شد — کسر از موجودی ادامه می‌یابد." if new_active else "🔴 سرویس ساعتی خاموش شد — دیگر کسر نمی‌شود."
            await q.edit_message_text(msg, reply_markup=service_card_keyboard(oid))
        except Exception as e:
            await q.edit_message_text(f"❌ خطا: {e}", reply_markup=service_card_keyboard(oid))
        return ConversationHandler.END

    # ---- قطع اعلان کسر ساعتی ----
    if data.startswith("svc_mutehourly_"):
        oid = int(data.replace("svc_mutehourly_", ""))
        o = get_user_order(oid, user.id)
        if not o:
            await q.answer("سرویس نامعتبر", show_alert=True)
            return ConversationHandler.END
        from db_products import update_order
        update_order(oid, hourly_notify_mute=1)
        await q.edit_message_text(
            f"🔕 اعلان کسر ساعتی برای سرویس #{oid} غیرفعال شد.\n"
            "کسر از موجودی ادامه دارد؛ فقط پیام اطلاع‌رسانی قطع شد."
        )
        return ConversationHandler.END

    # ---- تغییر لوکیشن (بین پنل‌ها) ----
    if data.startswith("svc_loc_") and not data.startswith("svc_locset_"):
        oid = _oid("svc_loc_")
        o = get_user_order(oid, user.id)
        if not o or not o.get("vpn_username"):
            await q.edit_message_text("سرویس معتبر نیست.", reply_markup=back_main_kb())
            return ConversationHandler.END
        if get_setting_sync("location_change_enabled", "1") != "1":
            await q.edit_message_text("تغییر لوکیشن فعلاً غیرفعال است.", reply_markup=service_card_keyboard(oid))
            return ConversationHandler.END
        from db_growth import count_location_changes
        from database import list_panels
        try:
            price = int(get_setting_sync("location_change_price", "0") or 0)
        except Exception:
            price = 0
        try:
            limit = int(get_setting_sync("location_change_limit", "3") or 3)
        except Exception:
            limit = 3
        used = count_location_changes(user.id)
        if limit > 0 and used >= limit:
            await q.edit_message_text(
                f"❌ به حد مجاز تغییر لوکیشن رسیده‌اید ({used}/{limit}).",
                reply_markup=service_card_keyboard(oid),
            )
            return ConversationHandler.END
        panels = list_panels() or []
        # filter active
        rows = []
        current_pid = o.get("panel_id")
        for pan in panels:
            if not pan.get("is_active", 1):
                continue
            mark = " ✅" if pan["id"] == current_pid else ""
            rows.append([InlineKeyboardButton(
                f"{pan['name']}{mark}"[:60],
                callback_data=f"svc_locset_{oid}_{pan['id']}",
            )])
        if not rows:
            await q.edit_message_text("پنل دیگری یافت نشد.", reply_markup=service_card_keyboard(oid))
            return ConversationHandler.END
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"svc_open_{oid}")])
        price_txt = f"{price:,} تومان" if price > 0 else "رایگان"
        await q.edit_message_text(
            f"🌍 تغییر لوکیشن (پنل)\n\n"
            f"قیمت هر بار: {price_txt}\n"
            f"استفاده‌شده: {used}/{limit if limit > 0 else '∞'}\n\n"
            f"پنل مقصد را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return ConversationHandler.END

    if data.startswith("svc_locset_"):
        # svc_locset_{orderId}_{newPanelId}
        parts = data.replace("svc_locset_", "").split("_")
        if len(parts) < 2:
            return ConversationHandler.END
        oid, new_panel_id = int(parts[0]), int(parts[1])
        o = get_user_order(oid, user.id)
        if not o or not o.get("vpn_username"):
            await q.edit_message_text("سرویس معتبر نیست.", reply_markup=back_main_kb())
            return ConversationHandler.END
        from db_growth import count_location_changes, record_location_change
        from database import get_panel_by_id, list_panels
        from services.pasarguard import PasarGuardClient, gb_to_bytes
        try:
            price = int(get_setting_sync("location_change_price", "0") or 0)
        except Exception:
            price = 0
        try:
            limit = int(get_setting_sync("location_change_limit", "3") or 3)
        except Exception:
            limit = 3
        used = count_location_changes(user.id)
        if limit > 0 and used >= limit:
            await q.edit_message_text("❌ به حد مجاز رسیده‌اید.", reply_markup=service_card_keyboard(oid))
            return ConversationHandler.END
        if o.get("panel_id") == new_panel_id:
            await q.edit_message_text("همین پنل فعال است.", reply_markup=service_card_keyboard(oid))
            return ConversationHandler.END
        bu = get_bot_user(user.id)
        balance = int((bu or {}).get("balance") or 0)
        if price > 0 and balance < price:
            await q.edit_message_text(
                f"❌ موجودی کافی نیست.\\nلازم: {price:,} / موجودی: {balance:,}",
                reply_markup=service_card_keyboard(oid),
            )
            return ConversationHandler.END
        new_panel = get_panel_by_id(new_panel_id)
        if not new_panel:
            await q.edit_message_text("پنل مقصد نامعتبر.", reply_markup=service_card_keyboard(oid))
            return ConversationHandler.END
        try:
            # خواندن وضعیت فعلی از پنل مبدا
            old_client = _client(o)
            full = old_client.get_user(o["vpn_username"])
            used_traffic = full.get("used_traffic") or 0
            data_limit = full.get("data_limit") or 0
            expire = full.get("expire")
            hwid = full.get("hwid_limit")
            status = full.get("status") or "active"
            # ساخت روی پنل جدید با همان مشخصات
            new_client = PasarGuardClient(
                new_panel["base_url"], new_panel["username"], new_panel["password"], verify_ssl=False
            )
            group_ids = []
            try:
                groups = new_client.get_groups() or []
                if groups:
                    group_ids = [groups[0].get("id") or groups[0]["id"]]
            except Exception:
                pass
            # username جدید
            import secrets, string
            new_uname = "fn" + "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
            remain_gb = None
            if data_limit and int(data_limit) > 0:
                remain_bytes = max(0, int(data_limit) - int(used_traffic))
                remain_gb = round(remain_bytes / (1024 ** 3), 2)
            payload = new_client.build_user_payload(
                username=new_uname,
                status=status,
                data_limit_gb=remain_gb if remain_gb is not None else 0,
                expire=expire,
                group_ids=group_ids,
                hwid_limit=hwid,
                note=f"reloc from order#{oid}",
                for_create=True,
            )
            created = new_client.create_user(payload)
            # حذف از پنل قدیم
            try:
                old_client.delete_user(o["vpn_username"])
            except Exception:
                pass
            if price > 0:
                add_balance(user.id, -price, f"location_change#{oid}")
            from db_products import update_order
            update_order(oid, vpn_username=created.get("username") or new_uname)
            # به‌روزرسانی panel_id — اگر ستون قابل آپدیت نباشد از SQL مستقیم
            try:
                from database import get_sync_connection
                conn = get_sync_connection()
                with conn.cursor() as cur:
                    cur.execute("UPDATE service_orders SET panel_id=%s, vpn_username=%s WHERE id=%s",
                                (new_panel_id, created.get("username") or new_uname, oid))
                    conn.commit()
                conn.close()
            except Exception as e:
                print("panel_id update", e)
            record_location_change(oid, user.id, from_gid=o.get("panel_id"), to_gid=new_panel_id,
                                   to_name=new_panel.get("name"), price=price)
            await q.edit_message_text(
                f"✅ لوکیشن به پنل «{new_panel.get('name')}» تغییر کرد."
                + (f"\\n💸 مبلغ کسرشده: {price:,} تومان" if price > 0 else ""),
                reply_markup=service_card_keyboard(oid),
            )
        except Exception as e:
            await q.edit_message_text(f"❌ تغییر لوکیشن ناموفق: {e}", reply_markup=service_card_keyboard(oid))
        return ConversationHandler.END

    if data.startswith("svc_report_"):
        oid = _oid("svc_report_")
        await q.edit_message_text(
            f"✅ گزارش اختلال برای #{oid} ثبت شد.",
            reply_markup=service_card_keyboard(oid),
        )
        try:
            await context.bot.send_message(ADMIN_ID, f"⚠️ گزارش اختلال سرویس #{oid} — کاربر {user.id}")
        except Exception:
            pass
        return ConversationHandler.END

    if data.startswith("svc_refund_"):
        oid = _oid("svc_refund_")
        await q.edit_message_text(
            f"✅ درخواست بازگشت وجه #{oid} ثبت شد. پشتیبانی بررسی می‌کند.",
            reply_markup=service_card_keyboard(oid),
        )
        try:
            await context.bot.send_message(ADMIN_ID, f"💸 عودت وجه سفارش #{oid} — کاربر {user.id}")
        except Exception:
            pass
        return ConversationHandler.END

    return ConversationHandler.END

# ---- پشتیبانی ساده: یک پیام = یک تیکت ----
async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_bot_user(user)
    text = get_template("support_welcome") or (
        "🛠 پشتیبانی\n\nپیام خود را بنویسید تا برای پشتیبانی ارسال شود.\n"
        "یا تیکت‌های قبلی را ببینید."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️ پیام جدید", callback_data="sup_new")],
        [InlineKeyboardButton("📋 تیکت‌های من", callback_data="sup_my")],
    ])
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)

async def support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    user = update.effective_user

    if data == "sup_new":
        deps = list_departments(active_only=True)
        if deps:
            rows = [[InlineKeyboardButton(d["name"], callback_data=f"sup_dep_{d['id']}")] for d in deps]
            rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="sup_back")])
            await q.edit_message_text("دپارتمان را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(rows))
        else:
            context.user_data["sup_dep"] = None
            await q.edit_message_text("پیام خود را بنویسید:")
            return WAITING_TICKET_MSG
        return ConversationHandler.END

    if data == "sup_back":
        await show_support(update, context)
        return ConversationHandler.END

    if data.startswith("sup_dep_"):
        context.user_data["sup_dep"] = int(data.replace("sup_dep_", ""))
        await q.edit_message_text("پیام خود را بنویسید:\n(یا /start برای انصراف)")
        return WAITING_TICKET_MSG

    if data == "sup_my":
        tickets = list_user_tickets(user.id)
        if not tickets:
            await q.edit_message_text(
                "تیکتی ندارید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="sup_back")]]),
            )
            return ConversationHandler.END
        rows = []
        for t in tickets[:15]:
            rows.append([InlineKeyboardButton(
                f"#{t['id']} · {t['status']}",
                callback_data=f"sup_open_{t['id']}",
            )])
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="sup_back")])
        await q.edit_message_text("تیکت‌های شما:", reply_markup=InlineKeyboardMarkup(rows))
        return ConversationHandler.END

    if data.startswith("sup_open_"):
        tid = int(data.replace("sup_open_", ""))
        t = get_ticket(tid)
        if not t or t["telegram_id"] != user.id:
            await q.edit_message_text("نامعتبر.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="sup_my")]]))
            return ConversationHandler.END
        msgs = get_ticket_messages(tid)
        lines = [f"تیکت #{tid} [{t['status']}]\n"]
        for m in msgs[-12:]:
            who = "شما" if m["sender"] == "user" else "پشتیبانی"
            lines.append(f"{who}: {m['message']}")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 ادامه گفتگو", callback_data=f"sup_dep_0")],  # will set ticket
            [InlineKeyboardButton("🔙 بازگشت", callback_data="sup_my")],
        ])
        context.user_data["sup_ticket"] = tid
        await q.edit_message_text("\n".join(lines)[:3500], reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 پیام جدید در این تیکت", callback_data=f"sup_cont_{tid}")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="sup_my")],
        ]))
        return ConversationHandler.END

    if data.startswith("sup_cont_"):
        tid = int(data.replace("sup_cont_", ""))
        context.user_data["sup_ticket"] = tid
        await q.edit_message_text("پیام خود را بنویسید:")
        return WAITING_TICKET_MSG

    return ConversationHandler.END

async def receive_ticket_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = (update.message.text or "").strip()
    if not msg:
        await update.message.reply_text("پیام خالی است. دوباره بنویسید:")
        return WAITING_TICKET_MSG
    tid = context.user_data.get("sup_ticket")
    if not tid:
        did = context.user_data.get("sup_dep")
        tid = create_ticket(user.id, did, msg[:80])
        context.user_data["sup_ticket"] = tid
    add_ticket_message(tid, "user", msg)
    await update.message.reply_text(
        f"✅ پیام در تیکت #{tid} ثبت شد.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 تیکت‌های من", callback_data="sup_my")],
            [InlineKeyboardButton("✍️ پیام دیگر", callback_data=f"sup_cont_{tid}")],
        ]),
    )
    try:
        await context.bot.send_message(
            ADMIN_ID,
            f"🎫 تیکت #{tid}\nکاربر: {user.id}\n{msg[:500]}",
        )
    except Exception:
        pass
    return ConversationHandler.END

async def receive_rename(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت نام سفارشی سرویس"""
    user = update.effective_user
    text = (update.message.text or "").strip()
    oid = context.user_data.get("rename_order_id")
    if not oid:
        await update.message.reply_text("جلسه منقضی شد.", reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_home")]]
        ))
        return ConversationHandler.END
    if text.lower() in ("/cancel", "cancel", "انصراف"):
        context.user_data.pop("rename_order_id", None)
        await update.message.reply_text(
            "❌ تغییر نام لغو شد.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_home")]]),
        )
        return ConversationHandler.END
    if text.lower() in ("/skip", "skip"):
        from db_products import update_order
        update_order(oid, custom_name=None)
        context.user_data.pop("rename_order_id", None)
        await update.message.reply_text(
            "✅ نام سفارشی حذف شد.",
            reply_markup=service_card_keyboard(oid),
        )
        return ConversationHandler.END
    name = text[:80]
    # بررسی تکراری بودن برای همین کاربر
    from db_support import list_user_orders
    others = list_user_orders(user.id)
    for o in others:
        if o["id"] != oid and (o.get("custom_name") or "").strip() == name:
            await update.message.reply_text(
                "❌ این نام قبلاً برای سرویس دیگری استفاده شده. نام دیگری بفرستید:\n/cancel برای انصراف"
            )
            return WAITING_RENAME
    from db_products import update_order
    update_order(oid, custom_name=name)
    context.user_data.pop("rename_order_id", None)
    await update.message.reply_text(
        f"✅ نام سرویس به «{name}» تغییر کرد.",
        reply_markup=service_card_keyboard(oid),
    )
    log_activity(user.id, "rename_service", f"{oid}:{name}")
    return ConversationHandler.END


# aliases for bot.py imports
async def receive_ticket_subject(update, context):
    return await receive_ticket_msg(update, context)

async def receive_ticket_reply(update, context):
    return await receive_ticket_msg(update, context)

WAITING_TICKET_SUBJECT = WAITING_TICKET_MSG
WAITING_TICKET_REPLY = WAITING_TICKET_MSG

async def show_education(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = get_template("education_text") or "📚 مرکز آموزش\nمتن را از پنل تنظیم کنید."
    if update.message:
        await update.message.reply_text(text)
    else:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text)
