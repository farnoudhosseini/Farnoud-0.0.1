from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import get_setting_sync, get_panel_by_id, list_panels
from db_growth import has_used_trial, record_trial
from db_users import upsert_bot_user, log_activity
from services.pasarguard import PasarGuardClient
from services.provision import fix_subscription_url, make_qr_png
from datetime import datetime, timedelta, timezone
import secrets, string, io
from telegram import InputFile


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
        client = PasarGuardClient(panel["base_url"], panel["username"], panel["password"], verify_ssl=False)
        uname = "tr" + "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
        groups = []
        try:
            g = client.get_groups()
            if g:
                groups = [g[0].get("id")]
        except Exception:
            pass
        exp = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        payload = client.build_user_payload(
            username=uname, status="active", data_limit_gb=vol, expire=exp,
            group_ids=groups, note=f"trial tg:{user.id}", for_create=True,
        )
        created = client.create_user(payload)
        full = client.get_user(created.get("username") or uname)
        raw = full.get("subscription_url") or full.get("subscription_link") or ""
        if not raw and full.get("subscription_token"):
            raw = f"/sub/{full['subscription_token']}"
        link = fix_subscription_url(panel["base_url"], raw)
        record_trial(user.id, panel["id"], uname)
        text = (
            f"🎁 اکانت تست — {panel.get('name')}\n"
            f"حجم: {vol} GB\nمدت: {days} روز\n"
            f"یوزرنیم: `{uname}`\n"
            f"لینک:\n{link}"
        )
        qr = make_qr_png(link)
        if qr:
            await context.bot.send_photo(
                user.id, photo=InputFile(io.BytesIO(qr), filename="trial.png"),
                caption=text[:1000], parse_mode="Markdown",
            )
        else:
            await context.bot.send_message(user.id, text, parse_mode="Markdown")
        log_activity(user.id, "trial", f"panel={panel_id}")
    except Exception as e:
        await context.bot.send_message(user.id, f"❌ خطا در ساخت تست: {e}")
