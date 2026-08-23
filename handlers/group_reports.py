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



def get_backup_interval_seconds() -> int:
    """فاصله بکاپ بر حسب ثانیه — حداقل 1 ساعت، پیش‌فرض 2 ساعت"""
    try:
        raw = get_setting_sync("backup_interval_hours", "2")
        hours = float(raw or 2)
    except Exception:
        hours = 2.0
    hours = max(1.0, min(hours, 168.0))  # 1h .. 7d
    return int(hours * 3600)


def reschedule_backup_job(application) -> float:
    """حذف جاب قبلی و ثبت دوباره با فاصله جدید. برمی‌گرداند hours."""
    jq = getattr(application, "job_queue", None)
    if not jq:
        return get_backup_interval_seconds() / 3600.0
    # remove existing backup jobs
    try:
        for job in list(jq.jobs()):
            name = getattr(job, "name", None) or ""
            cb = getattr(job, "callback", None)
            if name == "db_backup" or (cb and getattr(cb, "__name__", "") == "backup_job"):
                job.schedule_removal()
    except Exception as e:
        print("reschedule remove:", e)
    secs = get_backup_interval_seconds()
    jq.run_repeating(backup_job, interval=secs, first=30, name="db_backup")
    return secs / 3600.0

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


def _db_params():
    host = DB_CONFIG.get("host", "localhost")
    port = int(DB_CONFIG.get("port", 3306) or 3306)
    user = DB_CONFIG.get("user", "root")
    password = DB_CONFIG.get("password", "") or ""
    db = DB_CONFIG.get("db") or DB_CONFIG.get("database") or "farnoudbot"
    return host, port, user, password, db


def _mysqldump_bytes() -> tuple[bytes | None, str]:
    """برمی‌گرداند (data, error_message)"""
    host, port, user, password, db = _db_params()
    env = os.environ.copy()
    if password:
        env["MYSQL_PWD"] = password
    cmd = [
        "mysqldump",
        f"-h{host}",
        f"-P{port}",
        f"-u{user}",
        "--single-transaction",
        "--routines",
        "--triggers",
        "--events",
        "--default-character-set=utf8mb4",
        "--result-file=/dev/stdout",
        db,
    ]
    # بدون --result-file اگر پشتیبانی نشد
    cmd_simple = [
        "mysqldump",
        "-h", host,
        "-P", str(port),
        "-u", user,
        "--single-transaction",
        "--routines",
        "--triggers",
        "--default-character-set=utf8mb4",
        db,
    ]
    for c in (cmd_simple, cmd):
        try:
            proc = subprocess.run(
                c,
                capture_output=True,
                env=env,
                timeout=180,
            )
            if proc.returncode == 0 and proc.stdout:
                return proc.stdout, ""
            err = (proc.stderr or b"").decode("utf-8", errors="ignore")[:400]
            if "No such file" in err or "not found" in err.lower():
                return None, "mysqldump_not_found"
            last_err = err or f"exit {proc.returncode}"
        except FileNotFoundError:
            return None, "mysqldump_not_found"
        except Exception as e:
            last_err = str(e)
    return None, last_err if "last_err" in dir() else "mysqldump failed"


def _pymysql_export_bytes() -> tuple[bytes | None, str]:
    """اکسپورت با pymysql وقتی mysqldump نیست"""
    try:
        import pymysql
    except ImportError:
        return None, "pymysql نصب نیست"
    host, port, user, password, db = _db_params()
    try:
        conn = pymysql.connect(
            host=host, port=port, user=user, password=password,
            database=db, charset="utf8mb4",
            cursorclass=pymysql.cursors.SSCursor,
        )
    except Exception as e:
        return None, f"اتصال MySQL: {e}"
    lines = [
        f"-- FarnoudBot backup",
        f"-- Database: `{db}`",
        f"-- Date: {datetime.now().isoformat()}",
        "SET NAMES utf8mb4;",
        "SET FOREIGN_KEY_CHECKS=0;",
        "",
    ]
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW TABLES")
            tables = [r[0] for r in cur.fetchall()]
            for table in tables:
                cur.execute(f"SHOW CREATE TABLE `{table}`")
                row = cur.fetchone()
                create_sql = row[1] if row else ""
                lines.append(f"DROP TABLE IF EXISTS `{table}`;")
                lines.append(create_sql + ";")
                lines.append("")
                cur.execute(f"SELECT * FROM `{table}`")
                cols = [d[0] for d in cur.description] if cur.description else []
                while True:
                    batch = cur.fetchmany(200)
                    if not batch:
                        break
                    for rec in batch:
                        vals = []
                        for v in rec:
                            if v is None:
                                vals.append("NULL")
                            elif isinstance(v, (bytes, bytearray)):
                                vals.append("0x" + v.hex())
                            elif isinstance(v, (int, float)):
                                vals.append(str(v))
                            else:
                                s = str(v).replace("\\", "\\\\").replace("'", "\\'")
                                vals.append(f"'{s}'")
                        col_list = ", ".join(f"`{c}`" for c in cols)
                        lines.append(f"INSERT INTO `{table}` ({col_list}) VALUES ({', '.join(vals)});")
                lines.append("")
        lines.append("SET FOREIGN_KEY_CHECKS=1;")
        data = "\n".join(lines).encode("utf-8")
        return data, ""
    except Exception as e:
        return None, f"export: {e}"
    finally:
        try:
            conn.close()
        except Exception:
            pass


def export_database() -> tuple[bytes | None, str, str]:
    """
    returns (data, error, method)
    method: mysqldump | pymysql
    """
    data, err = _mysqldump_bytes()
    if data:
        return data, "", "mysqldump"
    if err != "mysqldump_not_found":
        # mysqldump هست ولی خطا داد — باز هم fallback
        pass
    data2, err2 = _pymysql_export_bytes()
    if data2:
        return data2, "", "pymysql"
    return None, (err2 or err or "unknown"), "none"


def _gzip_bytes(data: bytes) -> bytes:
    import gzip
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6) as gz:
        gz.write(data)
    return buf.getvalue()


async def send_db_backup(bot):
    """اکسپورت MySQL و ارسال به تاپیک backup"""
    gid = get_report_group()
    if not gid:
        print("backup: report group not set")
        return

    data, err, method = export_database()
    if not data:
        await send_report(
            bot, "backup",
            f"❌ بکاپ دیتابیس ناموفق بود.\n<code>{err}</code>",
        )
        return

    # فشرده‌سازی برای حجم کمتر
    try:
        payload = _gzip_bytes(data)
        fname = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql.gz"
        size_note = f"{len(data)/1024:.0f}KB → gzip {len(payload)/1024:.0f}KB"
    except Exception:
        payload = data
        fname = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        size_note = f"{len(data)/1024:.0f}KB"

    topic = get_report_topic("backup")
    caption = (
        f"💾 بکاپ دیتابیس\n"
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"🛠 روش: <code>{method}</code>\n"
        f"📦 {size_note}"
    )
    try:
        from telegram import InputFile
        kwargs = {
            "chat_id": gid,
            "document": InputFile(io.BytesIO(payload), filename=fname),
            "caption": caption,
            "parse_mode": "HTML",
        }
        if topic:
            kwargs["message_thread_id"] = int(topic)
        await bot.send_document(**kwargs)
    except Exception as e:
        print("backup send error:", e)
        await send_report(bot, "backup", f"❌ ارسال فایل بکاپ ناموفق:\n<code>{e}</code>")



async def backup_command(update, context):
    """ادمین: بکاپ فوری دیتابیس"""
    user = update.effective_user
    if not user or user.id != ADMIN_ID:
        return
    await update.message.reply_text("⏳ در حال تهیه بکاپ...")
    await send_db_backup(context.bot)
    await update.message.reply_text("✅ اگر گروه گزارش ست باشد، فایل به تاپیک بکاپ ارسال شد.")

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


async def auto_approve_job(context):
    """تایید خودکار رسیدهای کارت‌به‌کارت پس از گذشت زمان مشخص."""
    try:
        from database import get_setting_sync, get_sync_connection
        minutes = int(get_setting_sync("card_auto_approve_minutes", "0") or 0)
        if minutes <= 0:
            return
        conn = get_sync_connection()
        try:
            with conn.cursor() as cur:
                # charges
                cur.execute(
                    """SELECT id, telegram_id, amount FROM charge_requests
                       WHERE status='pending_review'
                         AND created_at < (NOW() - INTERVAL %s MINUTE)
                       LIMIT 30""",
                    (minutes,),
                )
                charges = cur.fetchall() or []
                # orders
                cur.execute(
                    """SELECT id, telegram_id, amount, wallet_used FROM service_orders
                       WHERE status='pending_review'
                         AND created_at < (NOW() - INTERVAL %s MINUTE)
                       LIMIT 30""",
                    (minutes,),
                )
                orders = cur.fetchall() or []
        finally:
            conn.close()
        from db_users import add_balance, get_charge
        from db_products import update_order, get_order
        from services.provision import provision_order
        bot = context.bot
        for ch in charges:
            try:
                add_balance(int(ch["telegram_id"]), int(ch["amount"]), f"charge#{ch['id']}")
                conn = get_sync_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE charge_requests SET status='approved' WHERE id=%s", (ch["id"],))
                        conn.commit()
                finally:
                    conn.close()
                try:
                    await bot.send_message(int(ch["telegram_id"]), f"شارژ #{ch['id']} به صورت خودکار تایید شد.")
                except Exception:
                    pass
            except Exception as e:
                print("auto charge", e)
        for o in orders:
            try:
                oid = int(o["id"])
                wu = int(o.get("wallet_used") or 0)
                if wu > 0:
                    try:
                        add_balance(int(o["telegram_id"]), -wu, f"order#{oid}")
                    except Exception:
                        pass
                update_order(oid, status="paid")
                result = provision_order(oid)
                try:
                    msg = "سفارش #%s به صورت خودکار تایید شد." % oid
                    if not result.get("ok"):
                        msg += " (خطا در ساخت: %s)" % (result.get("error") or "")
                    await bot.send_message(int(o["telegram_id"]), msg)
                except Exception:
                    pass
            except Exception as e:
                print("auto order", e)
    except Exception as e:
        print("auto_approve_job", e)
