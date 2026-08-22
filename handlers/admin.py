# پنل مدیریت داخل ربات تلگرام — شامل مدیریت پنل‌های VPN و کاربران پاسارگارد

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID
from database import get_setting, set_setting, list_panels, get_panel_by_id
from services.pasarguard import PasarGuardClient, bytes_to_gb

WAITING_WELCOME = 1
WAITING_USER_FIELD = 2  # ساخت/ویرایش کاربر چندمرحله‌ای

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 تنظیم پیام‌های ربات", callback_data="admin_msgs")],
        [InlineKeyboardButton("🖥 مدیریت پنل‌ها", callback_data="admin_panels")],
        [InlineKeyboardButton("📦 محصولات", callback_data="admin_products")],
        [InlineKeyboardButton("👥 کاربران ربات", callback_data="admin_bot_users")],
        [InlineKeyboardButton("💳 کارت‌ها / پرداخت", callback_data="admin_cards")],
        [InlineKeyboardButton("🧾 درخواست‌های شارژ", callback_data="admin_charges")],
        [InlineKeyboardButton("🔙 بستن", callback_data="admin_close")],
    ])

def panels_keyboard(panels):
    rows = []
    for p in panels:
        status = "🟢" if p.get("last_status") in ("online", "connected") else "⚪"
        rows.append([InlineKeyboardButton(
            f"{status} {p['name']} ({p['panel_type']})",
            callback_data=f"admin_panel_{p['id']}"
        )])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")])
    return InlineKeyboardMarkup(rows)

def panel_menu_keyboard(panel_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 وضعیت / آمار", callback_data=f"admin_pstats_{panel_id}")],
        [InlineKeyboardButton("👥 لیست کاربران VPN", callback_data=f"admin_pusers_{panel_id}")],
        [InlineKeyboardButton("➕ افزودن کاربر VPN", callback_data=f"admin_padduser_{panel_id}")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panels")],
    ])

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        if update.message:
            await update.message.reply_text("⛔️ دسترسی ندارید.")
        return
    text = "⚙️ <b>پنل مدیریت فرنود</b>\n\nاز دکمه‌های زیر استفاده کنید."
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=main_keyboard(), parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=main_keyboard(), parse_mode="HTML")

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    if not user or not is_admin(user.id):
        await query.edit_message_text("⛔️ دسترسی ندارید.")
        return ConversationHandler.END

    data = query.data

    if data == "admin_panel":
        await admin_panel(update, context)
        return ConversationHandler.END

    if data == "admin_view_welcome":
        current = await get_setting("welcome_message", "—")
        await query.edit_message_text(
            f"📄 <b>پیام خوش‌آمد فعلی:</b>\n\n{current}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    if data == "set_welcome":
        await query.edit_message_text(
            "📝 پیام خوش‌آمد جدید را ارسال کنید.\nبرای انصراف /start بزنید.",
            parse_mode="HTML",
        )
        return WAITING_WELCOME

    if data == "admin_close":
        await query.edit_message_text("✅ پنل بسته شد.")
        return ConversationHandler.END

    # ---- پنل‌ها ----
    if data == "admin_panels":
        panels = list_panels()
        if not panels:
            await query.edit_message_text(
                "هنوز پنلی متصل نیست.\nاز پنل وب اضافه کنید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]),
            )
            return ConversationHandler.END
        await query.edit_message_text(
            "🖥 <b>انتخاب پنل VPN:</b>",
            reply_markup=panels_keyboard(panels),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    if data.startswith("admin_panel_"):
        pid = int(data.replace("admin_panel_", ""))
        panel = get_panel_by_id(pid)
        if not panel:
            await query.edit_message_text("پنل یافت نشد.")
            return ConversationHandler.END
        await query.edit_message_text(
            f"🖥 <b>{panel['name']}</b>\n<code>{panel['base_url']}</code>\n\nیک گزینه را انتخاب کنید:",
            reply_markup=panel_menu_keyboard(pid),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    if data.startswith("admin_pstats_"):
        pid = int(data.replace("admin_pstats_", ""))
        panel = get_panel_by_id(pid)
        if not panel:
            await query.edit_message_text("پنل یافت نشد.")
            return ConversationHandler.END
        try:
            client = PasarGuardClient(panel["base_url"], panel["username"], panel["password"], verify_ssl=False)
            s = client.get_system_stats()
            cpu = s.get("cpu_usage", s.get("cpu", "—"))
            users = s.get("users") or {}
            total_u = s.get("total_user", s.get("users_total", users.get("total", "—")))
            active_u = s.get("users_active", s.get("active_users", users.get("active", "—")))
            text = (
                f"📊 <b>{panel['name']}</b> — آنلاین\n\n"
                f"CPU: <code>{cpu}</code>\n"
                f"کاربران: <code>{total_u}</code> (فعال: <code>{active_u}</code>)"
            )
        except Exception as e:
            text = f"❌ آفلاین\n<code>{e}</code>"
        await query.edit_message_text(
            text,
            reply_markup=panel_menu_keyboard(pid),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    if data.startswith("admin_pusers_"):
        pid = int(data.replace("admin_pusers_", ""))
        panel = get_panel_by_id(pid)
        if not panel:
            await query.edit_message_text("پنل یافت نشد.")
            return ConversationHandler.END
        try:
            client = PasarGuardClient(panel["base_url"], panel["username"], panel["password"], verify_ssl=False)
            data_u = client.get_users(offset=0, limit=20)
            users = data_u.get("users") or []
            if not users:
                text = "لیست کاربران خالی است."
                kb = panel_menu_keyboard(pid)
            else:
                rows = []
                lines = [f"👥 <b>کاربران {panel['name']}</b> (۲۰ تای اول)\n"]
                for u in users:
                    uname = u.get("username", "?")
                    st = u.get("status", "?")
                    lines.append(f"• <code>{uname}</code> — {st}")
                    rows.append([
                        InlineKeyboardButton(f"✏️ {uname}", callback_data=f"admin_pedit_{pid}_{uname}"),
                        InlineKeyboardButton("🗑", callback_data=f"admin_pdel_{pid}_{uname}"),
                    ])
                rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"admin_panel_{pid}")])
                text = "\n".join(lines)
                kb = InlineKeyboardMarkup(rows)
        except Exception as e:
            text = f"❌ خطا: <code>{e}</code>"
            kb = panel_menu_keyboard(pid)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return ConversationHandler.END

    if data.startswith("admin_pdel_"):
        # admin_pdel_{pid}_{username}
        rest = data.replace("admin_pdel_", "", 1)
        pid_str, _, uname = rest.partition("_")
        pid = int(pid_str)
        panel = get_panel_by_id(pid)
        if not panel:
            await query.edit_message_text("پنل یافت نشد.")
            return ConversationHandler.END
        try:
            PasarGuardClient(panel["base_url"], panel["username"], panel["password"], verify_ssl=False).delete_user(uname)
            await query.edit_message_text(
                f"✅ کاربر <code>{uname}</code> حذف شد.",
                reply_markup=panel_menu_keyboard(pid),
                parse_mode="HTML",
            )
        except Exception as e:
            await query.edit_message_text(f"❌ خطا: {e}", reply_markup=panel_menu_keyboard(pid))
        return ConversationHandler.END

    if data.startswith("admin_padduser_"):
        pid = int(data.replace("admin_padduser_", ""))
        panel = get_panel_by_id(pid)
        if not panel:
            await query.edit_message_text("پنل یافت نشد.")
            return ConversationHandler.END
        context.user_data["vpn_panel_id"] = pid
        context.user_data["vpn_mode"] = "create"
        context.user_data["vpn_user"] = {}
        context.user_data["vpn_step"] = "username"
        await query.edit_message_text(
            "➕ <b>ساخت کاربر VPN</b>\n\n"
            "نام کاربری را بفرستید (۳ تا ۳۲ کاراکتر، حروف/عدد/_):\n"
            "برای انصراف /start",
            parse_mode="HTML",
        )
        return WAITING_USER_FIELD

    if data.startswith("admin_pedit_"):
        rest = data.replace("admin_pedit_", "", 1)
        pid_str, _, uname = rest.partition("_")
        pid = int(pid_str)
        panel = get_panel_by_id(pid)
        if not panel:
            await query.edit_message_text("پنل یافت نشد.")
            return ConversationHandler.END
        context.user_data["vpn_panel_id"] = pid
        context.user_data["vpn_mode"] = "edit"
        context.user_data["vpn_edit_username"] = uname
        context.user_data["vpn_user"] = {}
        context.user_data["vpn_step"] = "data_limit"
        await query.edit_message_text(
            f"✏️ ویرایش <code>{uname}</code>\n\n"
            "حد حجم را به گیگابایت بفرستید (0 = نامحدود):\n"
            "یا بنویسید <code>-</code> برای رد کردن این فیلد.",
            parse_mode="HTML",
        )
        return WAITING_USER_FIELD


    if data == "admin_bot_users":
        from db_users import list_bot_users, ROLE_LABELS
        users, total = list_bot_users(limit=15)
        lines = [f"👥 کاربران ربات (نمایش ۱۵ از {total})\n"]
        rows = []
        for u in users:
            lines.append(f"• <code>{u['telegram_id']}</code> {u.get('username') or ''} — {ROLE_LABELS.get(u.get('role'), u.get('role'))} — {int(u.get('balance') or 0):,}")
            rows.append([InlineKeyboardButton(f"👤 {u['telegram_id']}", callback_data=f"admin_bu_{u['telegram_id']}")])
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")])
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
        return ConversationHandler.END

    if data.startswith("admin_bu_"):
        from db_users import get_bot_user, ROLE_LABELS, count_referrals, get_user_activity
        tid = int(data.replace("admin_bu_", ""))
        u = get_bot_user(tid)
        if not u:
            await query.edit_message_text("کاربر یافت نشد")
            return ConversationHandler.END
        refs = count_referrals(tid)
        text = (
            f"👤 <b>{u.get('first_name') or ''} {u.get('last_name') or ''}</b>\n"
            f"آیدی: <code>{u['telegram_id']}</code>\n"
            f"یوزرنیم: @{u.get('username') or '—'}\n"
            f"موبایل: {u.get('phone') or '—'}\n"
            f"موجودی: <b>{int(u.get('balance') or 0):,}</b> تومان\n"
            f"نقش: {ROLE_LABELS.get(u.get('role'), u.get('role'))}\n"
            f"زیرمجموعه: {refs}\n"
            f"مسدود: {'بله' if u.get('is_blocked') else 'خیر'}"
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("➕۱۰هزار", callback_data=f"admin_bal_{tid}_10000"),
                InlineKeyboardButton("➕۵۰هزار", callback_data=f"admin_bal_{tid}_50000"),
                InlineKeyboardButton("➕۱۰۰هزار", callback_data=f"admin_bal_{tid}_100000"),
            ],
            [
                InlineKeyboardButton("عادی", callback_data=f"admin_role_{tid}_user"),
                InlineKeyboardButton("نماینده", callback_data=f"admin_role_{tid}_reseller"),
            ],
            [
                InlineKeyboardButton("نماینده ویژه", callback_data=f"admin_role_{tid}_reseller_vip"),
                InlineKeyboardButton("VIP", callback_data=f"admin_role_{tid}_vip"),
            ],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_bot_users")],
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return ConversationHandler.END

    if data.startswith("admin_bal_"):
        from db_users import add_balance, get_bot_user
        parts = data.split("_")
        tid, amt = int(parts[2]), int(parts[3])
        add_balance(tid, amt, "admin_panel")
        u = get_bot_user(tid)
        await query.answer(f"موجودی: {int(u['balance']):,}", show_alert=True)
        # refresh
        query.data = f"admin_bu_{tid}"
        return await admin_callback(update, context)

    if data.startswith("admin_role_"):
        from db_users import update_bot_user
        parts = data.split("_")
        # admin_role_{tid}_{role}  role may be reseller_vip
        tid = int(parts[2])
        role = "_".join(parts[3:])
        update_bot_user(tid, role=role)
        await query.answer("نقش به‌روز شد", show_alert=True)
        query.data = f"admin_bu_{tid}"
        return await admin_callback(update, context)

    if data == "admin_cards":
        from db_users import list_cards
        cards = list_cards()
        lines = ["💳 کارت‌های تعریف‌شده:\n"] + [
            f"• {c['card_number']} — {c['owner_name']} ({'فعال' if c['is_active'] else 'غیرفعال'})"
            for c in cards
        ] or ["کارتی نیست. از پنل وب اضافه کنید."]
        await query.edit_message_text(
            "\n".join(lines) if cards else "کارتی ثبت نشده. از پنل وب اضافه کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]),
        )
        return ConversationHandler.END

    if data == "admin_charges":
        from db_users import list_pending_charges
        pending = list_pending_charges()
        if not pending:
            await query.edit_message_text(
                "درخواست معلقی نیست.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]),
            )
            return ConversationHandler.END
        rows = []
        lines = ["🧾 در انتظار تایید:\n"]
        for ch in pending[:20]:
            lines.append(f"#{ch['id']} — کاربر {ch['telegram_id']} — {int(ch['amount']):,} تومان")
            rows.append([
                InlineKeyboardButton(f"✅ #{ch['id']}", callback_data=f"adm_ch_ok_{ch['id']}"),
                InlineKeyboardButton(f"❌ #{ch['id']}", callback_data=f"adm_ch_no_{ch['id']}"),
            ])
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")])
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))
        return ConversationHandler.END

    if data.startswith("adm_ch_ok_"):
        from db_users import approve_charge, render_template, user_vars, get_bot_user
        cid = int(data.replace("adm_ch_ok_", ""))
        user = approve_charge(cid)
        if user:
            try:
                from db_users import get_charge
                ch = get_charge(cid)
                vars_ = user_vars(user)
                vars_["amount"] = f"{int(ch['amount']):,}"
                vars_["balance"] = f"{int(user['balance']):,}"
                await context.bot.send_message(user["telegram_id"], render_template("charge_approved", vars_))
            except Exception:
                pass
            await query.answer("تایید شد", show_alert=True)
            await query.edit_message_text(f"✅ فاکتور #{cid} تایید شد.")
        else:
            await query.answer("ناموفق", show_alert=True)
        return ConversationHandler.END

    if data.startswith("adm_ch_no_"):
        from db_users import reject_charge, get_charge, render_template, user_vars, get_bot_user
        cid = int(data.replace("adm_ch_no_", ""))
        ch = get_charge(cid)
        if reject_charge(cid, "توسط ادمین"):
            try:
                u = get_bot_user(ch["telegram_id"])
                vars_ = user_vars(u)
                vars_["amount"] = f"{int(ch['amount']):,}"
                vars_["reason"] = "توسط ادمین"
                await context.bot.send_message(ch["telegram_id"], render_template("charge_rejected", vars_))
            except Exception:
                pass
            await query.edit_message_text(f"❌ فاکتور #{cid} رد شد.")
        return ConversationHandler.END


    return ConversationHandler.END

async def receive_welcome_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        return ConversationHandler.END
    new_message = update.message.text.strip()
    if not new_message:
        await update.message.reply_text("❌ پیام خالی است.")
        return WAITING_WELCOME
    edit_key = context.user_data.pop("edit_msg_key", None)
    if edit_key:
        from db_users import set_template
        set_template(edit_key, new_message)
        await update.message.reply_text(f"✅ پیام <code>{edit_key}</code> ذخیره شد.", reply_markup=main_keyboard(), parse_mode="HTML")
        return ConversationHandler.END
    await set_setting("welcome_message", new_message)
    await update.message.reply_text("✅ ذخیره شد.", reply_markup=main_keyboard(), parse_mode="HTML")
    return ConversationHandler.END

async def receive_user_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """جمع‌آوری فیلدهای ساخت/ویرایش کاربر VPN به‌صورت گفتگو"""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return ConversationHandler.END

    text = (update.message.text or "").strip()
    step = context.user_data.get("vpn_step")
    mode = context.user_data.get("vpn_mode")
    pdata = context.user_data.setdefault("vpn_user", {})
    pid = context.user_data.get("vpn_panel_id")
    panel = get_panel_by_id(pid) if pid else None
    if not panel:
        await update.message.reply_text("پنل نامعتبر. از /admin دوباره شروع کنید.")
        return ConversationHandler.END

    if step == "username":
        if len(text) < 3 or len(text) > 32:
            await update.message.reply_text("نام کاربری نامعتبر. دوباره بفرستید:")
            return WAITING_USER_FIELD
        pdata["username"] = text
        context.user_data["vpn_step"] = "status"
        await update.message.reply_text("وضعیت را بفرستید:\n<code>active</code> یا <code>on_hold</code>", parse_mode="HTML")
        return WAITING_USER_FIELD

    if step == "status":
        if text not in ("active", "on_hold", "disabled"):
            await update.message.reply_text("فقط active / on_hold / disabled")
            return WAITING_USER_FIELD
        pdata["status"] = text
        if text == "on_hold":
            context.user_data["vpn_step"] = "on_hold_days"
            await update.message.reply_text("مدت on_hold به روز (مثلاً 30):")
            return WAITING_USER_FIELD
        context.user_data["vpn_step"] = "data_limit"
        await update.message.reply_text("حد حجم (گیگابایت) — 0 نامحدود:")
        return WAITING_USER_FIELD

    if step == "on_hold_days":
        try:
            days = int(text)
            if days <= 0:
                raise ValueError()
            pdata["on_hold_expire_duration"] = days * 86400
        except ValueError:
            await update.message.reply_text("عدد روز معتبر بفرستید:")
            return WAITING_USER_FIELD
        context.user_data["vpn_step"] = "data_limit"
        await update.message.reply_text("حد حجم (گیگابایت) — 0 نامحدود:")
        return WAITING_USER_FIELD

    if step == "data_limit":
        if text != "-":
            try:
                pdata["data_limit_gb"] = float(text)
            except ValueError:
                await update.message.reply_text("عدد معتبر بفرستید:")
                return WAITING_USER_FIELD
        context.user_data["vpn_step"] = "expire"
        await update.message.reply_text(
            "تاریخ پایان (مثال <code>2026-12-31</code>) یا 0 برای نامحدود:",
            parse_mode="HTML",
        )
        return WAITING_USER_FIELD

    if step == "expire":
        if text not in ("0", "-"):
            pdata["expire"] = text
        else:
            pdata["expire"] = None
        context.user_data["vpn_step"] = "groups"
        # لیست گروه‌ها
        try:
            client = PasarGuardClient(panel["base_url"], panel["username"], panel["password"], verify_ssl=False)
            groups = client.get_groups()
            context.user_data["vpn_groups"] = groups
            if groups:
                lines = ["شناسه گروه‌ها را با ویرگول بفرستید (یا 0 برای هیچ):"]
                for g in groups[:30]:
                    gid = g.get("id", g.get("id"))
                    lines.append(f"• {g.get('name', '?')} → <code>{gid}</code>")
                await update.message.reply_text("\n".join(lines), parse_mode="HTML")
            else:
                await update.message.reply_text("گروهی نیست. 0 بفرستید:")
        except Exception as e:
            await update.message.reply_text(f"گروه دریافت نشد ({e}). 0 بفرستید:")
        return WAITING_USER_FIELD

    if step == "groups":
        if text not in ("0", "-"):
            ids = [int(x) for x in text.replace(" ", "").split(",") if x.isdigit()]
            pdata["group_ids"] = ids
        else:
            pdata["group_ids"] = []
        context.user_data["vpn_step"] = "hwid"
        await update.message.reply_text("محدودیت HWID (تعداد دستگاه) یا 0 برای رد:")
        return WAITING_USER_FIELD

    if step == "hwid":
        if text not in ("0", "-"):
            try:
                pdata["hwid_limit"] = int(text)
            except ValueError:
                await update.message.reply_text("عدد معتبر:")
                return WAITING_USER_FIELD
        context.user_data["vpn_step"] = "note"
        await update.message.reply_text("توضیحات (یا - برای خالی):")
        return WAITING_USER_FIELD

    if step == "note":
        if text != "-":
            pdata["note"] = text
        # اجرا
        try:
            client = PasarGuardClient(panel["base_url"], panel["username"], panel["password"], verify_ssl=False)
            if mode == "create":
                payload = client.build_user_payload(
                    username=pdata.get("username"),
                    status=pdata.get("status", "active"),
                    data_limit_gb=pdata.get("data_limit_gb", 0),
                    expire=pdata.get("expire"),
                    group_ids=pdata.get("group_ids", []),
                    hwid_limit=pdata.get("hwid_limit"),
                    note=pdata.get("note"),
                    on_hold_expire_duration=pdata.get("on_hold_expire_duration"),
                    for_create=True,
                )
                u = client.create_user(payload)
                await update.message.reply_text(
                    f"✅ کاربر <code>{u.get('username', pdata.get('username'))}</code> ساخته شد.",
                    reply_markup=panel_menu_keyboard(pid),
                    parse_mode="HTML",
                )
            else:
                uname = context.user_data.get("vpn_edit_username")
                payload = client.build_user_payload(
                    status=pdata.get("status"),
                    data_limit_gb=pdata.get("data_limit_gb"),
                    expire=pdata.get("expire"),
                    group_ids=pdata.get("group_ids"),
                    hwid_limit=pdata.get("hwid_limit"),
                    note=pdata.get("note"),
                    on_hold_expire_duration=pdata.get("on_hold_expire_duration"),
                    for_create=False,
                )
                client.modify_user(uname, payload)
                await update.message.reply_text(
                    f"✅ کاربر <code>{uname}</code> ویرایش شد.",
                    reply_markup=panel_menu_keyboard(pid),
                    parse_mode="HTML",
                )
        except Exception as e:
            await update.message.reply_text(f"❌ خطا: {e}", reply_markup=panel_menu_keyboard(pid))
        context.user_data.pop("vpn_step", None)
        return ConversationHandler.END

    return ConversationHandler.END
