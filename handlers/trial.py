from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_setting_sync, get_panel_by_id, list_panels
from db_growth import has_used_trial, record_trial
from db_users import upsert_bot_user, log_activity
from db_products import create_order, update_order, list_products
from services.provision import provision_order, make_qr_png
from telegram import InputFile
import io
import html


def _trial_panels():
    """لیست پنل‌های مجاز برای تست — از تنظیم trial_panel_ids یا همه فعال‌ها"""
    raw = get_setting_sync("trial_panel_ids", "") or get_setting_sync("trial_panel_id", "")
    all_panels = list_panels() or []
    active = [p for p in all_panels if p.get("is_active", 1)]
    if not raw.strip():
        return active
    ids = set()
    for part in str(raw).replace(" ", "").split(","):
        if part.isdigit():
            ids.add(int(part))
    if not ids:
        return active
    return [p for p in active if p["id"] in ids]


def _pick_product_id():
    """یک product_id معتبر برای ثبت سفارش تست پیدا می‌کند."""
    try:
        prods = list_products(active_only=False) or []
        if prods:
            return int(prods[0]["id"])
    except Exception:
        pass
    return 1


async def start_trial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_bot_user(user)
    msg = update.message
    q = update.callback_query

    async def reply(text, **kw):
        if q:
            await q.answer()
            try:
                await q.edit_message_text(text, **kw)
            except Exception:
                await context.bot.send_message(user.id, text, **kw)
        elif msg:
            await msg.reply_text(text, **kw)

    if get_setting_sync("trial_enabled", "0") != "1":
        await reply("تست رایگان فعلاً غیرفعال است.")
        return
    if has_used_trial(user.id):
        await reply("شما قبلاً از تست رایگان استفاده کرده‌اید.")
        return
    panels = _trial_panels()
    if not panels:
        await reply("پنل تست تنظیم نشده. با پشتیبانی تماس بگیرید.")
        return
    if len(panels) == 1:
        return await _create_trial(update, context, panels[0]["id"])
    rows = [[InlineKeyboardButton(p["name"][:40], callback_data=f"trial_panel_{p['id']}")] for p in panels]
    rows.append([InlineKeyboardButton("🔙 منوی اصلی", callback_data="menu_home")])
    await reply("🎁 پنل تست را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(rows))


async def trial_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    if data.startswith("trial_panel_"):
        pid = int(data.replace("trial_panel_", ""))
        return await _create_trial(update, context, pid)


async def _create_trial(update: Update, context: ContextTypes.DEFAULT_TYPE, panel_id: int):
    """ساخت تست از طریق service_orders تا در «سرویس‌های من» نمایش داده شود."""
    user = update.effective_user
    q = update.callback_query
    msg = update.message

    async def reply(text, **kw):
        if q:
            try:
                await q.edit_message_text(text, **kw)
            except Exception:
                await context.bot.send_message(user.id, text, **kw)
        elif msg:
            await msg.reply_text(text, **kw)

    if has_used_trial(user.id):
        await reply("شما قبلاً از تست رایگان استفاده کرده‌اید.")
        return
    panel = get_panel_by_id(panel_id)
    if not panel:
        await reply("پنل تست یافت نشد.")
        return
    vol = float(get_setting_sync("trial_volume_gb", "1") or 1)
    days = int(get_setting_sync("trial_days", "1") or 1)
    await reply("⏳ در حال ساخت اکانت تست...")
    try:
        product_id = _pick_product_id()
        order_id = create_order(user.id, product_id, panel_id, 0, 0, 0)

        protocol_override = None
        try:
            import json
            raw = get_setting_sync("trial_protocols_json", "") or "{}"
            all_cfg = json.loads(raw) if raw else {}
            cfg = all_cfg.get(str(panel_id)) or all_cfg.get(panel_id) or {}
            if cfg and (cfg.get("inbound_ids") or cfg.get("group_ids")):
                protocol_override = json.dumps(cfg, ensure_ascii=False)
        except Exception as e:
            print("trial protocol cfg:", e)

        update_kwargs = dict(
            status="paid",
            wallet_used=0,
            pay_amount=0,
            volume_gb_override=vol,
            duration_days_override=days,
            custom_name="تست رایگان",
        )
        if protocol_override:
            update_kwargs["protocol_override"] = protocol_override
        update_order(order_id, **update_kwargs)

        result = provision_order(order_id)
        if not result.get("ok"):
            err = html.escape(str(result.get("error") or "ساخت تست ناموفق")[:300])
            await context.bot.send_message(
                user.id,
                f"❌ خطا در ساخت تست: {err}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_home")]]
                ),
            )
            return

        uname = result.get("vpn_username") or ""
        link = result.get("subscription_link") or ""
        try:
            record_trial(user.id, panel["id"], uname)
        except Exception as e:
            print("record_trial:", e)

        panel_name = html.escape(str(panel.get("name") or ""))
        uname_safe = html.escape(str(uname))
        link_safe = html.escape(str(link))
        text = (
            f"🎁 اکانت تست — {panel_name}\n"
            f"حجم: {vol} GB\nمدت: {days} روز\n"
            f"یوزرنیم: <code>{uname_safe}</code>\n"
            f"لینک:\n<code>{link_safe}</code>"
        )
        qr = result.get("qr_bytes") or (make_qr_png(link) if link else None)
        if qr:
            await context.bot.send_photo(
                user.id,
                photo=InputFile(io.BytesIO(qr), filename="trial.png"),
                caption=text[:1000],
                parse_mode="HTML",
            )
        else:
            await context.bot.send_message(user.id, text, parse_mode="HTML")
        await context.bot.send_message(
            user.id,
            "👇",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("📱 سرویس‌های من", callback_data="menu_services")],
                    [InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_home")],
                ]
            ),
        )
        log_activity(user.id, "trial", f"panel={panel_id},order={order_id}")
    except Exception as e:
        err = html.escape(str(e)[:300])
        await context.bot.send_message(
            user.id,
            f"❌ خطا در ساخت تست: {err}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 منوی اصلی", callback_data="menu_home")]]
            ),
        )
