from telegram import Update
from telegram.ext import ContextTypes
from database import get_setting_sync, get_panel_by_id
from db_growth import has_used_trial, record_trial
from db_users import upsert_bot_user, log_activity
from services.pasarguard import PasarGuardClient
from services.provision import fix_subscription_url, make_qr_png, ensure_service_template
from db_users import render_template, set_template, get_template
from datetime import datetime, timedelta, timezone
import secrets, string, io
from telegram import InputFile

async def start_trial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_bot_user(user)
    if get_setting_sync("trial_enabled", "0") != "1":
        await update.message.reply_text("تست رایگان فعلاً غیرفعال است.")
        return
    if has_used_trial(user.id):
        await update.message.reply_text("شما قبلاً از تست رایگان استفاده کرده‌اید.")
        return
    panel_id = get_setting_sync("trial_panel_id", "")
    if not panel_id:
        await update.message.reply_text("پنل تست تنظیم نشده. با پشتیبانی تماس بگیرید.")
        return
    panel = get_panel_by_id(int(panel_id))
    if not panel:
        await update.message.reply_text("پنل تست یافت نشد.")
        return
    vol = float(get_setting_sync("trial_volume_gb", "1") or 1)
    days = int(get_setting_sync("trial_days", "1") or 1)
    await update.message.reply_text("⏳ در حال ساخت اکانت تست...")
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
        link = fix_subscription_url(panel["base_url"], raw)
        record_trial(user.id, panel["id"], uname)
        text = (
            f"🎁 اکانت تست\n"
            f"حجم: {vol} GB\nمدت: {days} روز\n"
            f"یوزرنیم: `{uname}`\n"
            f"لینک:\n{link}"
        )
        qr = make_qr_png(link)
        if qr:
            await context.bot.send_photo(user.id, photo=InputFile(io.BytesIO(qr), filename="trial.png"), caption=text[:1000], parse_mode="Markdown")
        else:
            await update.message.reply_text(text, parse_mode="Markdown")
        log_activity(user.id, "trial")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در ساخت تست: {e}")
