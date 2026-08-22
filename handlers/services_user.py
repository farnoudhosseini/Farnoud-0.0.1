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
from services.provision import fix_subscription_url, make_qr_png
from database import get_setting_sync
import io
from datetime import datetime, timedelta, timezone

WAITING_TICKET_MSG = 31

def _panel_creds(o: dict):
    base = o.get("base_url") or o.get("panel_base") or ""
    user = o.get("panel_user") or o.get("username")
    # password field from join
    pwd = o.get("panel_pass") or o.get("password")
    return base, user, pwd

def _client(o: dict) -> PasarGuardClient:
    base, user, pwd = _panel_creds(o)
    if not base or not user:
        raise RuntimeError("اطلاعات پنل ناقص است")
    return PasarGuardClient(base, user, pwd or "", verify_ssl=False)

def back_main_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="svc_list")]])

def service_card_keyboard(order_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 تمدید خودکار", callback_data=f"svc_renew_{order_id}")],
        [
            InlineKeyboardButton("🔐 بازنشانی اشتراک", callback_data=f"svc_reset_{order_id}"),
            InlineKeyboardButton("⏯ خاموش / روشن", callback_data=f"svc_toggle_{order_id}"),
        ],
        [InlineKeyboardButton("📎 لینک و QR", callback_data=f"svc_link_{order_id}")],
        [
            InlineKeyboardButton("⚠️ گزارش اختلال", callback_data=f"svc_report_{order_id}"),
            InlineKeyboardButton("💸 بازگشت وجه", callback_data=f"svc_refund_{order_id}"),
        ],
        [InlineKeyboardButton("🔙 لیست سرویس‌ها", callback_data="svc_list")],
    ])

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
        title = o.get("product_name") or f"سفارش #{o['id']}"
        uname = o.get("vpn_username") or "—"
        rows.append([InlineKeyboardButton(f"🔷 {title} · {uname}", callback_data=f"svc_open_{o['id']}")])
    rows.append([InlineKeyboardButton("🛒 خرید سرویس جدید", callback_data="buy_go")])
    text = "📱 سرویس‌های من\nیکی را انتخاب کنید:"
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

    if data.startswith("svc_open_"):
        oid = int(data.split("_")[-1])
        o = get_user_order(oid, user.id)
        if not o:
            await q.edit_message_text("سرویس پیدا نشد.", reply_markup=back_main_kb())
            return ConversationHandler.END
        text = (
            f"🔷 <b>{o.get('product_name') or 'سرویس'}</b>\n\n"
            f"شماره: <code>{o['id']}</code>\n"
            f"یوزرنیم: <code>{o.get('vpn_username') or '—'}</code>\n"
            f"پنل: {o.get('panel_name') or '—'}\n"
            f"حجم: {o.get('volume_gb') or '—'} GB\n"
            f"مدت: {o.get('duration_days') or '—'} روز\n"
            f"وضعیت سفارش: {o.get('status')}"
        )
        await q.edit_message_text(text, reply_markup=service_card_keyboard(oid), parse_mode="HTML")
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

    if data.startswith("svc_renew_"):
        oid = _oid("svc_renew_")
        o = get_user_order(oid, user.id)
        if not o or not o.get("vpn_username"):
            await q.edit_message_text("اکانت نیست.", reply_markup=back_main_kb())
            return ConversationHandler.END
        product = get_product(o["product_id"]) if o.get("product_id") else None
        price = int((product or {}).get("price") or o.get("amount") or 0)
        days = int((product or {}).get("duration_days") or o.get("duration_days") or 30)
        volume = float((product or {}).get("volume_gb") or o.get("volume_gb") or 0)
        bu = get_bot_user(user.id)
        balance = int((bu or {}).get("balance") or 0)
        if price > 0 and balance < price:
            await q.edit_message_text(
                f"موجودی کافی نیست.\nقیمت تمدید: {price:,} تومان\nموجودی: {balance:,}\nاز کیف پول شارژ کنید.",
                reply_markup=service_card_keyboard(oid),
            )
            return ConversationHandler.END
        try:
            if price > 0:
                add_balance(user.id, -price, f"renew#{oid}")
            client = _client(o)
            uname = o["vpn_username"]
            full = client.get_user(uname)
            # extend expire
            exp = full.get("expire")
            now = datetime.now(timezone.utc)
            base_dt = now
            if exp:
                try:
                    if isinstance(exp, (int, float)) and exp > 0:
                        base_dt = datetime.fromtimestamp(int(exp), tz=timezone.utc)
                    else:
                        base_dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
                    if base_dt < now:
                        base_dt = now
                except Exception:
                    base_dt = now
            new_exp = (base_dt + timedelta(days=days)).isoformat()
            payload = {"expire": new_exp, "status": "active"}
            if volume > 0:
                payload["data_limit"] = int(volume * 1024 ** 3)
            # reset usage optional
            try:
                client._request("POST", f"/api/user/{uname}/reset")
            except Exception:
                pass
            client.modify_user(uname, payload)
            await q.edit_message_text(
                f"✅ سرویس {days} روز تمدید شد.\nمبلغ کسرشده: {price:,} تومان",
                reply_markup=service_card_keyboard(oid),
            )
            log_activity(user.id, "renew", str(oid))
        except Exception as e:
            if price > 0:
                try:
                    add_balance(user.id, price, f"renew_refund#{oid}")
                except Exception:
                    pass
            await q.edit_message_text(f"❌ تمدید ناموفق: {e}", reply_markup=service_card_keyboard(oid))
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
