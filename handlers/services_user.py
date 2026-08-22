# سرویس‌های من + پشتیبانی + آموزش

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID
from db_users import get_template, render_template, log_activity, upsert_bot_user
from db_support import (
    list_user_orders, get_user_order, list_departments, create_ticket,
    add_ticket_message, list_user_tickets, get_ticket, get_ticket_messages, close_ticket,
)
from services.pasarguard import PasarGuardClient
from services.provision import fix_subscription_url, make_qr_png, send_service_to_user
import io

WAITING_TICKET_SUBJECT = 30
WAITING_TICKET_MSG = 31
WAITING_TICKET_REPLY = 32

def service_card_keyboard(order_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 تمدید", callback_data=f"svc_renew_{order_id}"),
            InlineKeyboardButton("🔐 بازنشانی اشتراک", callback_data=f"svc_reset_{order_id}"),
        ],
        [
            InlineKeyboardButton("⏯ خاموش/روشن", callback_data=f"svc_toggle_{order_id}"),
            InlineKeyboardButton("📎 لینک و QR", callback_data=f"svc_link_{order_id}"),
        ],
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
        text = "هنوز سرویسی خریداری نکرده‌اید."
        if update.message:
            await update.message.reply_text(text)
        else:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text)
        return
    rows = []
    for o in orders:
        title = o.get("product_name") or f"سفارش #{o['id']}"
        uname = o.get("vpn_username") or "—"
        rows.append([InlineKeyboardButton(
            f"🔷 {title} ({uname})",
            callback_data=f"svc_open_{o['id']}",
        )])
    text = "📱 سرویس‌های شما:\nیکی را انتخاب کنید:"
    kb = InlineKeyboardMarkup(rows)
    if update.message:
        await update.message.reply_text(text, reply_markup=kb)
    else:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=kb)
    log_activity(user.id, "my_services")

async def services_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    user = update.effective_user

    if data == "svc_list":
        await show_my_services(update, context)
        return ConversationHandler.END

    if data.startswith("svc_open_"):
        oid = int(data.replace("svc_open_", ""))
        o = get_user_order(oid, user.id)
        if not o:
            await q.edit_message_text("سرویس یافت نشد.")
            return ConversationHandler.END
        text = (
            f"🔷 <b>{o.get('product_name') or 'سرویس'}</b>\n"
            f"شماره سفارش: <code>{o['id']}</code>\n"
            f"یوزرنیم VPN: <code>{o.get('vpn_username') or '—'}</code>\n"
            f"پنل: {o.get('panel_name') or '—'}\n"
            f"حجم: {o.get('volume_gb') or '—'} GB | مدت: {o.get('duration_days') or '—'} روز\n"
            f"وضعیت سفارش: {o.get('status')}"
        )
        await q.edit_message_text(text, reply_markup=service_card_keyboard(oid), parse_mode="HTML")
        return ConversationHandler.END

    if data.startswith("svc_link_"):
        oid = int(data.replace("svc_link_", ""))
        o = get_user_order(oid, user.id)
        if not o or not o.get("vpn_username"):
            await q.edit_message_text("اکانت متصل نیست.")
            return ConversationHandler.END
        try:
            client = PasarGuardClient(o["base_url"], o["panel_user"], o["panel_pass"], verify_ssl=False)
            full = client.get_user(o["vpn_username"])
            raw = full.get("subscription_url") or full.get("subscription_link") or ""
            if not raw and full.get("subscription_token"):
                raw = f"/sub/{full['subscription_token']}"
            link = fix_subscription_url(o.get("base_url") or "", raw)
            text = f"لینک اتصال:\n{link}"
            qr = make_qr_png(link)
            if qr:
                from telegram import InputFile
                await context.bot.send_photo(
                    user.id, photo=InputFile(io.BytesIO(qr), filename="qr.png"), caption=text[:1000]
                )
                await q.edit_message_text("لینک و QR ارسال شد.", reply_markup=service_card_keyboard(oid))
            else:
                await q.edit_message_text(text, reply_markup=service_card_keyboard(oid))
        except Exception as e:
            await q.edit_message_text(f"خطا: {e}", reply_markup=service_card_keyboard(oid))
        return ConversationHandler.END

    if data.startswith("svc_reset_"):
        oid = int(data.replace("svc_reset_", ""))
        o = get_user_order(oid, user.id)
        if not o or not o.get("vpn_username"):
            await q.edit_message_text("اکانت نیست.")
            return ConversationHandler.END
        try:
            client = PasarGuardClient(o["base_url"], o["panel_user"], o["panel_pass"], verify_ssl=False)
            # revoke subscription
            client._request("POST", f"/api/user/{o['vpn_username']}/revoke")
            await q.edit_message_text(
                "✅ اشتراک بازنشانی شد. لینک قبلی غیرفعال است؛ از «لینک و QR» لینک جدید بگیرید.",
                reply_markup=service_card_keyboard(oid),
            )
        except Exception as e:
            await q.edit_message_text(f"خطا: {e}", reply_markup=service_card_keyboard(oid))
        return ConversationHandler.END

    if data.startswith("svc_toggle_"):
        oid = int(data.replace("svc_toggle_", ""))
        o = get_user_order(oid, user.id)
        if not o or not o.get("vpn_username"):
            await q.edit_message_text("اکانت نیست.")
            return ConversationHandler.END
        try:
            client = PasarGuardClient(o["base_url"], o["panel_user"], o["panel_pass"], verify_ssl=False)
            full = client.get_user(o["vpn_username"])
            st = (full.get("status") or "active").lower()
            # disabled toggle API
            disabled = st not in ("disabled",)
            client._request("PUT", f"/api/user/{o['vpn_username']}/disabled", json={"disabled": disabled})
            new_st = "غیرفعال" if disabled else "فعال"
            await q.edit_message_text(f"✅ سرویس اکنون {new_st} شد.", reply_markup=service_card_keyboard(oid))
        except Exception as e:
            # fallback modify status
            try:
                new_status = "disabled" if st == "active" else "active"
                client.modify_user(o["vpn_username"], {"status": new_status})
                await q.edit_message_text(f"✅ وضعیت → {new_status}", reply_markup=service_card_keyboard(oid))
            except Exception as e2:
                await q.edit_message_text(f"خطا: {e2}", reply_markup=service_card_keyboard(oid))
        return ConversationHandler.END

    if data.startswith("svc_renew_"):
        oid = int(data.replace("svc_renew_", ""))
        await q.edit_message_text(
            "🔄 برای تمدید، از «خرید سرویس جدید» همان محصول را بخرید یا با پشتیبانی هماهنگ کنید.\n"
            "(تمدید خودکار در آپدیت بعدی کامل‌تر می‌شود.)",
            reply_markup=service_card_keyboard(oid),
        )
        return ConversationHandler.END

    if data.startswith("svc_report_"):
        oid = int(data.replace("svc_report_", ""))
        await q.edit_message_text(
            f"⚠️ گزارش اختلال برای سفارش #{oid} ثبت شد. از پشتیبانی هم می‌توانید تیکت باز کنید.",
            reply_markup=service_card_keyboard(oid),
        )
        try:
            await context.bot.send_message(ADMIN_ID, f"⚠️ گزارش اختلال سرویس #{oid} از کاربر {user.id}")
        except Exception:
            pass
        return ConversationHandler.END

    if data.startswith("svc_refund_"):
        oid = int(data.replace("svc_refund_", ""))
        await q.edit_message_text(
            f"💸 درخواست بازگشت وجه برای #{oid} ثبت شد. پشتیبانی بررسی می‌کند.",
            reply_markup=service_card_keyboard(oid),
        )
        try:
            await context.bot.send_message(ADMIN_ID, f"💸 درخواست عودت وجه سفارش #{oid} کاربر {user.id}")
        except Exception:
            pass
        return ConversationHandler.END

    return ConversationHandler.END

# ---- support ----
async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    upsert_bot_user(user)
    deps = list_departments(active_only=True)
    text = get_template("support_welcome") or "🛠 پشتیبانی\nدپارتمان را انتخاب کنید:"
    rows = [[InlineKeyboardButton(d["name"], callback_data=f"sup_dep_{d['id']}")] for d in deps]
    rows.append([InlineKeyboardButton("📋 تیکت‌های من", callback_data="sup_my")])
    kb = InlineKeyboardMarkup(rows)
    if update.message:
        await update.message.reply_text(text, reply_markup=kb)
    else:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=kb)

async def support_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    user = update.effective_user

    if data == "sup_my":
        tickets = list_user_tickets(user.id)
        if not tickets:
            await q.edit_message_text("تیکتی ندارید.")
            return ConversationHandler.END
        rows = [[InlineKeyboardButton(
            f"#{t['id']} {t['subject'][:20]} ({t['status']})",
            callback_data=f"sup_open_{t['id']}",
        )] for t in tickets]
        await q.edit_message_text("تیکت‌های شما:", reply_markup=InlineKeyboardMarkup(rows))
        return ConversationHandler.END

    if data.startswith("sup_dep_"):
        did = int(data.replace("sup_dep_", ""))
        context.user_data["sup_dep"] = did
        await q.edit_message_text("موضوع تیکت را در یک خط بنویسید:")
        return WAITING_TICKET_SUBJECT

    if data.startswith("sup_open_"):
        tid = int(data.replace("sup_open_", ""))
        t = get_ticket(tid)
        if not t or t["telegram_id"] != user.id:
            await q.edit_message_text("تیکت نامعتبر.")
            return ConversationHandler.END
        msgs = get_ticket_messages(tid)
        lines = [f"تیکت #{tid} — {t['subject']} [{t['status']}]\n"]
        for m in msgs[-15:]:
            who = "شما" if m["sender"] == "user" else "پشتیبانی"
            lines.append(f"{who}: {m['message']}")
        context.user_data["sup_ticket"] = tid
        rows = [
            [InlineKeyboardButton("💬 پاسخ", callback_data=f"sup_reply_{tid}")],
            [InlineKeyboardButton("بستن تیکت", callback_data=f"sup_close_{tid}")],
        ]
        await q.edit_message_text("\n".join(lines)[:3500], reply_markup=InlineKeyboardMarkup(rows))
        return ConversationHandler.END

    if data.startswith("sup_reply_"):
        tid = int(data.replace("sup_reply_", ""))
        context.user_data["sup_ticket"] = tid
        await q.edit_message_text("پیام خود را بنویسید:")
        return WAITING_TICKET_REPLY

    if data.startswith("sup_close_"):
        tid = int(data.replace("sup_close_", ""))
        close_ticket(tid)
        await q.edit_message_text(f"تیکت #{tid} بسته شد.")
        return ConversationHandler.END

    return ConversationHandler.END

async def receive_ticket_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subject = (update.message.text or "").strip()
    if not subject:
        await update.message.reply_text("موضوع خالی است:")
        return WAITING_TICKET_SUBJECT
    did = context.user_data.get("sup_dep")
    tid = create_ticket(update.effective_user.id, did, subject)
    context.user_data["sup_ticket"] = tid
    await update.message.reply_text(f"تیکت #{tid} باز شد. متن پیام را بنویسید:")
    return WAITING_TICKET_MSG

async def receive_ticket_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = context.user_data.get("sup_ticket")
    msg = (update.message.text or "").strip()
    if not tid or not msg:
        return ConversationHandler.END
    add_ticket_message(tid, "user", msg)
    await update.message.reply_text("✅ پیام ثبت شد. از «تیکت‌های من» می‌توانید ادامه دهید.")
    try:
        await context.bot.send_message(
            ADMIN_ID,
            f"🎫 تیکت #{tid}\nکاربر: {update.effective_user.id}\n{msg[:500]}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("پاسخ در پنل وب", callback_data=f"admin_panel"),
            ]]),
        )
    except Exception:
        pass
    return ConversationHandler.END

async def receive_ticket_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await receive_ticket_msg(update, context)

async def show_education(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = get_template("education_text") or "📚 مرکز آموزش\nمتن از پنل قابل تنظیم است."
    if update.message:
        await update.message.reply_text(text)
    else:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text)
