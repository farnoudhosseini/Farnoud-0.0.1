# /setgroup — گزارش‌ها در گروه تاپیک‌دار + بکاپ دیتابیس

from __future__ import annotations
import io
import os
import subprocess
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_ID, DB_CONFIG
from database import get_setting_sync, set_setting_sync
from db_extras import (
    get_report_group, set_report_group, get_report_topic, set_report_topic,
)

TOPIC_KINDS = {
    "sales": "🛒 فروش و سرویس",
    "charges": "💳 شارژ و پرداخت",
    "tickets": "🎫 تیکت و پشتیبانی",
    "errors": "⚠️ خطاها",
    "backup": "💾 بکاپ دیتابیس",
}


async def setgroup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فقط ادمین ربات — در گروه فروم/تاپیک اجرا شود"""
    user = update.effective_user
    chat = update.effective_chat
    if not user or user.id != ADMIN_ID:
        # سکوت برای غیر ادمین
        return
    if not chat or chat.type not in ("group", "supergroup"):
        await update.message.reply_text("این دستور فقط داخل گروه قابل استفاده است.")
        return

    set_report_group(chat.id)
    # ساخت تاپیک برای هر نوع گزارش (اگر گروه فروم باشد)
    created = []
    for kind, title in TOPIC_KINDS.items():
        try:
            topic = await context.bot.create_forum_topic(chat.id, name=title)
            tid = topic.message_thread_id
            set_report_topic(kind, tid)
            created.append(f"✅ {title} → topic {tid}")
        except Exception as e:
            # ممکن است گروه فروم نباشد
            created.append(f"⚠️ {title}: {e}")

    await update.message.reply_text(
        f"📢 گروه گزارش ست شد.\nChat ID: <code>{chat.id}</code>\n\n"
        + "\n".join(created),
        parse_mode="HTML",
    )


async def send_report(bot, kind: str, text: str, parse_mode: str = "HTML"):
    """ارسال گزارش به تاپیک مربوطه"""
    gid = get_report_group()
    if not gid:
        return
    topic = get_report_topic(kind)
    kwargs = {"chat_id": gid, "text": text[:4000], "parse_mode": parse_mode}
    if topic:
        kwargs["message_thread_id"] = topic
    try:
        await bot.send_message(**kwargs)
    except Exception as e:
        print(f"report send error ({kind}): {e}")


def _mysqldump_bytes() -> bytes | None:
    host = DB_CONFIG.get("host", "localhost")
    port = str(DB_CONFIG.get("port", 3306))
    user = DB_CONFIG.get("user", "root")
    password = DB_CONFIG.get("password", "")
    db = DB_CONFIG.get("db") or DB_CONFIG.get("database", "farnoudbot")
    env = os.environ.copy()
    if password:
        env["MYSQL_PWD"] = password
    try:
        proc = subprocess.run(
            ["mysqldump", "-h", host, "-P", port, "-u", user, "--single-transaction", db],
            capture_output=True,
            env=env,
            timeout=120,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
        print("mysqldump err:", proc.stderr[:300] if proc.stderr else "unknown")
        return None
    except Exception as e:
        print("mysqldump exception:", e)
        return None


async def send_db_backup(bot):
    """ارسال بکاپ دیتابیس به تاپیک backup"""
    gid = get_report_group()
    if not gid:
        return
    data = _mysqldump_bytes()
    if not data:
        await send_report(bot, "backup", "❌ بکاپ دیتابیس ناموفق بود.")
        return
    topic = get_report_topic("backup")
    fname = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    kwargs = {
        "chat_id": gid,
        "document": io.BytesIO(data),
        "filename": fname,
        "caption": f"💾 بکاپ دیتابیس — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    }
    if topic:
        kwargs["message_thread_id"] = topic
    try:
        # python-telegram-bot InputFile
        from telegram import InputFile
        kwargs["document"] = InputFile(io.BytesIO(data), filename=fname)
        await bot.send_document(**kwargs)
    except Exception as e:
        print("backup send error:", e)


async def backup_job(context: ContextTypes.DEFAULT_TYPE):
    await send_db_backup(context.bot)


async def hourly_job(context: ContextTypes.DEFAULT_TYPE):
    from services.service_edit import process_hourly_charges
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    results = process_hourly_charges()
    for r in results:
        oid = r.get("order_id")
        tid = r.get("telegram_id")
        if r.get("stopped") and tid:
            try:
                await context.bot.send_message(
                    tid,
                    f"⏹ سرویس ساعتی #{oid} به دلیل کمبود موجودی متوقف شد.",
                )
            except Exception:
                pass
            await send_report(
                context.bot,
                "errors",
                f"⏹ سرویس ساعتی #{oid} به دلیل کمبود موجودی متوقف شد.",
            )
        elif r.get("charged") and tid and not r.get("mute_notify"):
            charge = int(r.get("charged") or 0)
            hours = int(r.get("hours") or 1)
            bal = r.get("balance_after")
            bal_txt = f"\nموجودی باقی‌مانده: {int(bal):,} تومان" if bal is not None else ""
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "🔕 قطع اعلان کسر این سرویس",
                    callback_data=f"svc_mutehourly_{oid}",
                )],
            ])
            try:
                await context.bot.send_message(
                    tid,
                    f"⏱ کسر هزینه ساعتی\n"
                    f"سرویس #{oid}\n"
                    f"مبلغ: {charge:,} تومان ({hours} ساعت){bal_txt}",
                    reply_markup=kb,
                )
            except Exception:
                pass
