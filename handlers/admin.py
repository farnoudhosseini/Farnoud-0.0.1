# پنل مدیریت داخل ربات تلگرام — شامل مدیریت پنل‌ها و کاربران پاسارگارد

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID
from database import get_setting, set_setting, list_panels, get_panel_by_id
from services.pasarguard import PasarGuardClient, bytes_to_gb

WAITING_WELCOME = 1
WAITING_USER_FIELD = 2  # ساخت/ویرایش کاربر چندمرحله‌ای
WAITING_ADMIN_TEXT = 41  # جستجو/ارسال همگانی/تنظیمات مدیریت

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 تنظیم پیام‌های ربات", callback_data="admin_msgs"),
         InlineKeyboardButton("👋 خوش‌آمدگویی", callback_data="admin_welcome")],
        [InlineKeyboardButton("🖥 مدیریت پنل‌ها", callback_data="admin_panels")],
        [InlineKeyboardButton("📦 محصولات", callback_data="admin_products")],
        [InlineKeyboardButton("📋 سرویس‌های فروخته‌شده", callback_data="admin_orders")],
        [InlineKeyboardButton("👥 کاربران ربات", callback_data="admin_bot_users")],
        [InlineKeyboardButton("📣 ارسال همگانی", callback_data="admin_broadcast"),
         InlineKeyboardButton("🔎 جستجوی کاربر", callback_data="admin_user_search")],
        [InlineKeyboardButton("🛠 وب‌پنل", callback_data="admin_web"),
         InlineKeyboardButton("🎁 رفرال", callback_data="admin_referral")],
        [InlineKeyboardButton("💳 کارت‌ها / پرداخت", callback_data="admin_cards")],
        [InlineKeyboardButton("🧾 درخواست‌های شارژ", callback_data="admin_charges")],
        [
            InlineKeyboardButton("✨ ایموجی پریمیوم", callback_data="admin_premiji"),
            InlineKeyboardButton("⌨️ منوی شیشه‌ای", callback_data="admin_inline_menu"),
        ],
        [InlineKeyboardButton("⏱ سرویس ساعتی", callback_data="admin_hourly")],
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
        [InlineKeyboardButton("📦 سقف فروش", callback_data=f"admin_pmax_{panel_id}")],
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
            "🖥 <b>انتخاب پنل:</b>",
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

    if data.startswith("admin_pmax_"):
        pid=int(data.replace("admin_pmax_",""))
        panel=get_panel_by_id(pid)
        context.user_data["admin_input_mode"]="panel_max"
        context.user_data["admin_panel_id"]=pid
        await query.edit_message_text(
            f"📦 سقف فروش «{panel['name'] if panel else '—'}» را بفرستید.\n۰ = بدون محدودیت."
        )
        return WAITING_ADMIN_TEXT

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
            mem = s.get("mem_used") or s.get("memory_used")
            mem_t = s.get("mem_total") or s.get("memory_total")
            mem_s = f"{mem}/{mem_t}" if mem is not None else "—"
            text = (
                f"📊 <b>{panel['name']}</b>\n"
                f"وضعیت: ✅ آنلاین\n"
                f"آدرس: <code>{panel['base_url']}</code>\n"
                f"نوع: {panel.get('panel_type')}\n\n"
                f"CPU: <code>{cpu}</code>\n"
                f"رم: <code>{mem_s}</code>\n"
                f"کاربران کل: <code>{total_u}</code>\n"
                f"کاربران فعال: <code>{active_u}</code>"
            )
        except Exception as e:
            text = (
                f"📊 <b>{panel['name']}</b>\n"
                f"وضعیت: ❌ آفلاین\n"
                f"آدرس: <code>{panel['base_url']}</code>\n"
                f"خطا: <code>{e}</code>"
            )
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


    if data=="admin_referral":
        from database import get_setting_sync
        pct=get_setting_sync("referral_percent","10"); signup=get_setting_sync("referral_signup_bonus","0")
        cap=get_setting_sync("referral_monthly_cap","0"); minimum=get_setting_sync("referral_min_amount","0")
        await query.edit_message_text(
            f"🎁 <b>سیستم رفرال</b>\n\nپورسانت: {pct}%\nپاداش ثبت‌نام: {signup} تومان\nحداقل خرید مشمول: {minimum} تومان\nسقف ماهانه: {cap or '∞'} تومان",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("درصد پورسانت",callback_data="admin_ref_pct"),
                 InlineKeyboardButton("پاداش ثبت‌نام",callback_data="admin_ref_signup")],
                [InlineKeyboardButton("حداقل مبلغ",callback_data="admin_ref_min"),
                 InlineKeyboardButton("سقف ماهانه",callback_data="admin_ref_cap")],
                [InlineKeyboardButton("🔙 بازگشت",callback_data="admin_panel")]
            ]))
        return ConversationHandler.END

    if data.startswith("admin_ref_") and data in ("admin_ref_pct","admin_ref_signup","admin_ref_min","admin_ref_cap"):
        context.user_data["admin_input_mode"]="ref_"+data.replace("admin_ref_","")
        await query.edit_message_text("مقدار جدید را فقط به صورت عدد بفرستید:")
        return WAITING_ADMIN_TEXT

    if data == "admin_user_search":
        context.user_data["admin_input_mode"] = "search_users"
        await query.edit_message_text("🔎 آیدی، یوزرنیم، نام یا شماره کاربر را بفرستید:")
        return WAITING_ADMIN_TEXT

    if data == "admin_broadcast":
        await query.edit_message_text(
            "📣 نوع ارسال را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("همگانی", callback_data="admin_bc_all"),
                 InlineKeyboardButton("دارای موجودی", callback_data="admin_bc_balance")],
                [InlineKeyboardButton("بدون موجودی", callback_data="admin_bc_nobalance"),
                 InlineKeyboardButton("دارای زیرمجموعه", callback_data="admin_bc_refs")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")],
            ]),
        )
        return ConversationHandler.END

    if data.startswith("admin_bc_"):
        mode=data.replace("admin_bc_","")
        context.user_data["admin_broadcast_mode"]=mode
        context.user_data["admin_input_mode"]="broadcast"
        await query.edit_message_text(
            "📝 متن پیام را بفرستید.\n\nمی‌توانید از متغیرهای استاندارد پیام‌ها استفاده کنید. "
            "در مرحله بعد، پین و دکمه اصلی قابل تنظیم است."
        )
        return WAITING_ADMIN_TEXT

    if data == "admin_web":
        from database import get_sync_connection
        conn=get_sync_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT username FROM admins ORDER BY id LIMIT 1")
                row=cur.fetchone()
        finally:
            conn.close()
        await query.edit_message_text(
            f"🛠 <b>مدیریت وب‌پنل</b>\n\n"
            f"نام کاربری فعلی: <code>{(row or {}).get('username','—')}</code>\n"
            "از گزینه‌های زیر می‌توانید اعتبار ورود را تغییر دهید.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ تغییر نام کاربری", callback_data="admin_web_user")],
                [InlineKeyboardButton("🔐 تغییر رمز عبور", callback_data="admin_web_pass")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")],
            ]),
        )
        return ConversationHandler.END

    if data in ("admin_web_user","admin_web_pass"):
        context.user_data["admin_input_mode"]="web_user" if data.endswith("user") else "web_pass"
        await query.edit_message_text("مقدار جدید را بفرستید:")
        return WAITING_ADMIN_TEXT

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
        cards=list_cards()
        rows=[[InlineKeyboardButton("➕ افزودن کارت",callback_data="admin_card_add")]]
        lines=["💳 <b>مدیریت کارت‌ها</b>\n"]
        for c in cards:
            lines.append(f"• <code>{c['card_number']}</code> — {c['owner_name']} — {'فعال' if c['is_active'] else 'خاموش'}")
            rows.append([
                InlineKeyboardButton(("خاموش" if c['is_active'] else "روشن"),callback_data=f"admin_card_toggle_{c['id']}_{0 if c['is_active'] else 1}"),
                InlineKeyboardButton("🗑 حذف",callback_data=f"admin_card_del_{c['id']}")
            ])
        rows.append([InlineKeyboardButton("🔙 بازگشت",callback_data="admin_panel")])
        await query.edit_message_text("\n".join(lines) if cards else "هنوز کارتی ثبت نشده.",reply_markup=InlineKeyboardMarkup(rows),parse_mode="HTML")
        return ConversationHandler.END

    if data=="admin_card_add":
        context.user_data["admin_input_mode"]="card_add"
        await query.edit_message_text("شماره کارت | نام صاحب | نام بانک را در یک خط بفرستید.\nنمونه:\n6037... | Farnoud | Mellat")
        return WAITING_ADMIN_TEXT

    if data.startswith("admin_card_toggle_"):
        rest=data.replace("admin_card_toggle_","",1).split("_",1)
        cid,active=rest[0],rest[1]
        from db_users import toggle_card
        toggle_card(int(cid),active=="1")
        context.user_data["admin_input_mode"]=None
        query.data="admin_cards"
        return await admin_callback(update,context)

    if data.startswith("admin_card_del_"):
        from db_users import delete_card
        delete_card(int(data.replace("admin_card_del_","")))
        query.data="admin_cards"
        return await admin_callback(update,context)

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



    if data=="admin_welcome":
        from database import get_setting_sync
        context.user_data["admin_input_mode"]="welcome_all"
        await query.edit_message_text(
            "📝 پیام خوش‌آمدگویی /start را بفرستید.\nمتغیرها و کدهای premium مانند p_xxxxxxxx فعال هستند."
        )
        return WAITING_ADMIN_TEXT

    if data == "admin_msgs":
        try:
            from db_users import list_templates
            tpls = list_templates()
        except Exception as e:
            await query.edit_message_text(f"خطا: {e}")
            return ConversationHandler.END
        if not tpls:
            await query.edit_message_text(
                "قالب پیامی نیست. یک‌بار ربات را ری‌استارت کنید تا ساخته شود.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]),
            )
            return ConversationHandler.END
        lines = ["📝 <b>تنظیم پیام‌های ربات</b>\nیک مورد را انتخاب کنید:\n"]
        rows = []
        for tp in tpls[:20]:
            lines.append(f"• {tp.get('title') or tp['key']}")
            rows.append([InlineKeyboardButton((tp.get('title') or tp['key'])[:40], callback_data=f"admin_msg_{tp['key']}")])
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")])
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
        return ConversationHandler.END

    if data.startswith("admin_msg_"):
        key = data[len("admin_msg_"):]
        from db_users import get_template
        body = get_template(key) or "(خالی)"
        context.user_data["edit_msg_key"] = key
        await query.edit_message_text(
            f"✏️ پیام <code>{key}</code>\n\n{body[:800]}\n\n———\nمتن جدید را همین الان بفرستید:\nمتغیرها: [username] [balance] [invite_link] ...",
            parse_mode="HTML",
        )
        return WAITING_WELCOME

    if data == "admin_products":
        try:
            from db_products import list_products, ROLE_OPTIONS
            products = list_products()
        except Exception as e:
            await query.edit_message_text(
                f"خطا در محصولات: {e}\nاز پنل وب هم می‌توانید مدیریت کنید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]),
            )
            return ConversationHandler.END
        lines = ["📦 <b>محصولات</b>\n"]
        for pr in products[:25]:
            lines.append(f"• {pr['name']} — {int(pr['price']):,} ت — {pr.get('volume_gb')}GB / {pr.get('duration_days')}روز")
        if not products:
            lines.append("محصولی نیست. از پنل وب اضافه کنید.")
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    if data.startswith("adm_ord_ok_"):
        from db_products import get_order, update_order
        from db_users import add_balance
        from services.provision import provision_order, send_service_to_user
        oid = int(data.replace("adm_ord_ok_", ""))
        order = get_order(oid)
        if not order:
            await query.answer("یافت نشد", show_alert=True)
            return ConversationHandler.END
        if order["status"] not in ("pending_review", "paid"):
            await query.answer(f"وضعیت: {order['status']}", show_alert=True)
            return ConversationHandler.END
        wu = int(order.get("wallet_used") or 0)
        if wu > 0:
            try:
                add_balance(order["telegram_id"], -wu, f"order#{oid}")
            except Exception as e:
                print("deduct", e)
        update_order(oid, status="paid")
        await query.edit_message_text(f"⏳ ساخت سرویس #{oid}...")
        result = provision_order(oid)
        try:
            await send_service_to_user(context.bot, order["telegram_id"], result)
        except Exception as e:
            print("send", e)
        if result.get("ok"):
            await query.edit_message_text(f"✅ سفارش #{oid} تایید و سرویس تحویل شد.")
        else:
            await query.edit_message_text(f"⚠️ پرداخت OK — خطای ساخت: {result.get('error')}")
        return ConversationHandler.END

    if data.startswith("adm_ord_no_"):
        from db_products import get_order, update_order
        oid = int(data.replace("adm_ord_no_", ""))
        order = get_order(oid)
        if order:
            update_order(oid, status="rejected")
            try:
                await context.bot.send_message(order["telegram_id"], f"❌ سفارش #{oid} رد شد.")
            except Exception:
                pass
            await query.edit_message_text(f"❌ سفارش #{oid} رد شد.")
        return ConversationHandler.END

    # ---- سرویس‌های فروخته‌شده ----
    if data == "admin_orders":
        from db_products import list_all_orders
        orders = list_all_orders(status="provisioned", limit=15)
        if not orders:
            await query.edit_message_text(
                "سرویس فعالی نیست.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]),
            )
            return ConversationHandler.END
        rows = []
        for o in orders:
            label = f"#{o['id']} {o.get('vpn_username') or '—'} ({o.get('product_name') or ''})"
            rows.append([InlineKeyboardButton(label[:50], callback_data=f"admin_ord_{o['id']}")])
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")])
        await query.edit_message_text("📋 سرویس‌های فعال (آخرین ۱۵):", reply_markup=InlineKeyboardMarkup(rows))
        return ConversationHandler.END

    if data.startswith("admin_ord_") and not data.startswith("admin_ordedit_"):
        from db_products import get_order_full
        oid = int(data.replace("admin_ord_", ""))
        o = get_order_full(oid)
        if not o:
            await query.edit_message_text("یافت نشد.")
            return ConversationHandler.END
        vol = o.get("volume_gb_override") or o.get("volume_gb") or "—"
        days = o.get("duration_days_override") or o.get("duration_days") or "—"
        text = (
            f"📋 سرویس #{o['id']}\n"
            f"کاربر: {o.get('telegram_id')}\n"
            f"VPN: <code>{o.get('vpn_username') or '—'}</code>\n"
            f"محصول: {o.get('product_name') or '—'}\n"
            f"پنل: {o.get('panel_name') or '—'}\n"
            f"حجم: {vol} GB | مدت: {days} روز\n"
            f"ساعتی: {'بله' if o.get('is_hourly') else 'خیر'} | فعال: {o.get('hourly_active')}\n"
            f"وضعیت: {o.get('status')}"
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📦 حجم", callback_data=f"admin_ordedit_{oid}_vol"),
                InlineKeyboardButton("📅 روز", callback_data=f"admin_ordedit_{oid}_days"),
            ],
            [
                InlineKeyboardButton("📱 HWID", callback_data=f"admin_ordedit_{oid}_hwid"),
                InlineKeyboardButton("⏯ وضعیت", callback_data=f"admin_ordedit_{oid}_status"),
            ],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_orders")],
        ])
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return ConversationHandler.END

    if data.startswith("admin_ordedit_"):
        # admin_ordedit_{oid}_{field}
        parts = data.replace("admin_ordedit_", "").split("_")
        if len(parts) < 2:
            return ConversationHandler.END
        oid, field = int(parts[0]), parts[1]
        context.user_data["ord_edit_id"] = oid
        context.user_data["ord_edit_field"] = field
        prompts = {
            "vol": "حجم جدید (گیگابایت) را بفرستید (۰ = نامحدود):",
            "days": "تعداد روز باقی‌مانده از الان را بفرستید:",
            "hwid": "محدودیت HWID را بفرستید (۰ = نامحدود):",
            "status": "وضعیت را بفرستید: active یا disabled",
        }
        await query.edit_message_text(prompts.get(field, "مقدار را بفرستید:"))
        return WAITING_USER_FIELD

    # ---- ایموجی پریمیوم ----
    if data == "admin_premiji":
        from db_extras import list_premium_emojis
        items = list_premium_emojis()
        lines = ["✨ <b>ایموجی‌های پریمیوم</b>\n"]
        rows = [[InlineKeyboardButton("➕ افزودن", callback_data="admin_premiji_add")]]
        for e in items[:20]:
            lines.append(f"<code>{e['code']}</code> → <code>{e['custom_emoji_id']}</code>")
            rows.append([
                InlineKeyboardButton(f"🗑 {e['code']}", callback_data=f"admin_premiji_del_{e['code']}"),
            ])
        rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")])
        if len(lines) == 1:
            lines.append("هنوز چیزی ثبت نشده.")
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")
        return ConversationHandler.END

    if data == "admin_premiji_add":
        context.user_data["premiji_step"] = "code"
        await query.edit_message_text(
            "کد را وارد کنید (باید با <code>p_</code> شروع شود).\n"
            "یا خالی بفرستید تا کد تصادفی ساخته شود.",
            parse_mode="HTML",
        )
        return WAITING_USER_FIELD

    if data.startswith("admin_premiji_del_"):
        from db_extras import delete_premium_emoji
        code = data.replace("admin_premiji_del_", "", 1)
        delete_premium_emoji(code)
        await query.edit_message_text(f"حذف شد: {code}", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 لیست", callback_data="admin_premiji")],
        ]))
        return ConversationHandler.END

    # ---- منوی شیشه‌ای ----
    if data == "admin_inline_menu":
        from database import get_setting_sync, set_setting_sync
        cur = get_setting_sync("inline_main_menu", "0")
        new = "0" if cur == "1" else "1"
        set_setting_sync("inline_main_menu", new)
        state = "شیشه‌ای (اینلاین) ✅" if new == "1" else "دکمه‌ای (ریپلای) ✅"
        await query.edit_message_text(
            f"⌨️ منوی اصلی ربات: <b>{state}</b>\n\nکاربران با /start منوی جدید را می‌بینند.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]),
            parse_mode="HTML",
        )
        return ConversationHandler.END

    # ---- ساعتی ----
    if data == "admin_hourly":
        from database import get_setting_sync, set_setting_sync
        cur = get_setting_sync("hourly_global_enabled", "0")
        await query.edit_message_text(
            f"⏱ سرویس ساعتی سراسری: {'فعال ✅' if cur == '1' else 'غیرفعال ❌'}\n\n"
            "می‌توانید برای هر محصول هم hourly را جداگانه در وب‌پنل فعال کنید.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "خاموش کردن" if cur == "1" else "روشن کردن",
                    callback_data="admin_hourly_toggle",
                )],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")],
            ]),
        )
        return ConversationHandler.END

    if data == "admin_hourly_toggle":
        from database import get_setting_sync, set_setting_sync
        cur = get_setting_sync("hourly_global_enabled", "0")
        set_setting_sync("hourly_global_enabled", "0" if cur == "1" else "1")
        # reuse
        data = "admin_hourly"
        # fall through by recursive style - just re-show
        cur2 = get_setting_sync("hourly_global_enabled", "0")
        await query.edit_message_text(
            f"⏱ سرویس ساعتی سراسری: {'فعال ✅' if cur2 == '1' else 'غیرفعال ❌'}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "خاموش کردن" if cur2 == "1" else "روشن کردن",
                    callback_data="admin_hourly_toggle",
                )],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")],
            ]),
        )
        return ConversationHandler.END

    return ConversationHandler.END

async def receive_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.effective_user
    if not user or not is_admin(user.id):
        return ConversationHandler.END
    text=(update.message.text or "").strip()
    mode=context.user_data.pop("admin_input_mode",None)

    if mode=="search_users":
        from db_users import list_bot_users, ROLE_LABELS
        users,total=list_bot_users(limit=15,search=text)
        rows=[]
        lines=[f"🔎 نتیجه جستجو: {total} کاربر\n"]
        for u in users:
            lines.append(f"• <code>{u['telegram_id']}</code> @{u.get('username') or '—'} — {int(u.get('balance') or 0):,}")
            rows.append([InlineKeyboardButton(f"👤 {u['telegram_id']}",callback_data=f"admin_bu_{u['telegram_id']}")])
        rows.append([InlineKeyboardButton("🔎 جستجوی دوباره",callback_data="admin_user_search")])
        rows.append([InlineKeyboardButton("🔙 مدیریت",callback_data="admin_panel")])
        await update.message.reply_text("\n".join(lines),reply_markup=InlineKeyboardMarkup(rows),parse_mode="HTML")
        return ConversationHandler.END

    if mode=="welcome_all":
        from database import set_setting_sync
        set_setting_sync("welcome_message",text)
        await update.message.reply_text("✅ پیام خوش‌آمدگویی ذخیره شد.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📝 پیام‌ها",callback_data="admin_msgs")]]))
        return ConversationHandler.END

    if mode and mode.startswith("ref_"):
        from database import set_setting_sync
        keymap={"pct":"referral_percent","signup":"referral_signup_bonus","min":"referral_min_amount","cap":"referral_monthly_cap"}
        key=keymap.get(mode[4:])
        if not text.isdigit():
            await update.message.reply_text("فقط عدد وارد کنید.")
            return ConversationHandler.END
        set_setting_sync(key,text)
        await update.message.reply_text("✅ تنظیم رفرال ذخیره شد.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎁 رفرال",callback_data="admin_referral")]]))
        return ConversationHandler.END

    if mode=="panel_max":
        if not text.isdigit():
            await update.message.reply_text("فقط عدد وارد کنید.")
            return ConversationHandler.END
        pid=int(context.user_data.pop("admin_panel_id",0))
        from database import get_sync_connection
        conn=get_sync_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE vpn_panels SET max_sales=%s WHERE id=%s",(None if int(text)==0 else int(text),pid))
                conn.commit()
        finally: conn.close()
        await update.message.reply_text("✅ سقف فروش ذخیره شد.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🖥 پنل‌ها",callback_data="admin_panels")]]))
        return ConversationHandler.END

    if mode=="card_add":
        parts=[x.strip() for x in text.split("|")]
        if len(parts)<2 or not parts[0] or not parts[1]:
            await update.message.reply_text("فرمت نامعتبر است. شماره | صاحب | بانک")
            return ConversationHandler.END
        from db_users import add_card
        add_card(parts[0],parts[1],parts[2] if len(parts)>2 and parts[2] else None)
        await update.message.reply_text("✅ کارت اضافه شد.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💳 کارت‌ها",callback_data="admin_cards")]]))
        return ConversationHandler.END

    if mode=="web_user":
        from database import get_sync_connection
        conn=get_sync_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE admins SET username=%s WHERE id=(SELECT id FROM (SELECT id FROM admins ORDER BY id LIMIT 1) x)",(text[:50],))
            conn.commit()
        finally: conn.close()
        await update.message.reply_text("✅ نام کاربری وب‌پنل تغییر کرد.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 مدیریت",callback_data="admin_panel")]]))
        return ConversationHandler.END

    if mode=="web_pass":
        from database import get_sync_connection
        conn=get_sync_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE admins SET password=%s WHERE id=(SELECT id FROM (SELECT id FROM admins ORDER BY id LIMIT 1) x)",(text,))
            conn.commit()
        finally: conn.close()
        await update.message.reply_text("✅ رمز وب‌پنل تغییر کرد.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 مدیریت",callback_data="admin_panel")]]))
        return ConversationHandler.END

    if mode=="broadcast":
        context.user_data["admin_broadcast_text"]=text
        context.user_data["admin_input_mode"]="broadcast_opts"
        await update.message.reply_text(
            "⚙️ تنظیمات ارسال را بفرستید:\n"
            "pin=1 برای پین کردن / pin=0 بدون پین\n"
            "button=1 برای افزودن دکمه «منوی اصلی» / button=0 بدون دکمه\n"
            "نمونه: pin=1 button=1"
        )
        return WAITING_ADMIN_TEXT

    if mode=="broadcast_opts":
        import re
        opts=dict(re.findall(r"(pin|button)\\s*=\\s*(0|1)",text.lower()))
        pin=opts.get("pin","0")=="1"; button=opts.get("button","0")=="1"
        msg=context.user_data.pop("admin_broadcast_text","")
        bc=context.user_data.pop("admin_broadcast_mode","all")
        from db_users import list_bot_users, user_vars
        users,_=list_bot_users(limit=100000)
        sent=0
        for u in users:
            bal=int(u.get("balance") or 0)
            refs=__import__("db_users").count_referrals(u["telegram_id"])
            if not (bc=="all" or (bc=="balance" and bal>0) or (bc=="nobalance" and bal<=0) or (bc=="refs" and refs>0)):
                continue
            try:
                from db_extras import apply_premium_emojis
                body=apply_premium_emojis(msg)
                kb=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منوی اصلی",callback_data="menu_home")]]) if button else None
                m=await context.bot.send_message(u["telegram_id"],body,parse_mode="HTML",reply_markup=kb)
                if pin:
                    try: await context.bot.pin_chat_message(u["telegram_id"],m.message_id,disable_notification=True)
                    except Exception: pass
                sent+=1
            except Exception:
                pass
        await update.message.reply_text(f"✅ ارسال انجام شد.\nموفق: {sent}")
        return ConversationHandler.END

    await update.message.reply_text("ورودی نامعتبر است.")
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
    """جمع‌آوری فیلدهای ساخت/ویرایش کاربر VPN به‌صورت گفتگو + ادیت سفارش + ایموجی پریمیوم"""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return ConversationHandler.END

    text = (update.message.text or "").strip()

    # ---- ادیت سرویس فروخته‌شده ----
    if context.user_data.get("ord_edit_id") and context.user_data.get("ord_edit_field"):
        from services.service_edit import edit_sold_service
        oid = context.user_data.pop("ord_edit_id")
        field = context.user_data.pop("ord_edit_field")
        kwargs = {}
        try:
            if field == "vol":
                kwargs["volume_gb"] = float(text)
            elif field == "days":
                kwargs["duration_days"] = int(text)
            elif field == "hwid":
                kwargs["hwid_limit"] = int(text)
            elif field == "status":
                if text not in ("active", "disabled", "on_hold"):
                    await update.message.reply_text("فقط active / disabled / on_hold")
                    context.user_data["ord_edit_id"] = oid
                    context.user_data["ord_edit_field"] = field
                    return WAITING_USER_FIELD
                kwargs["status"] = text
        except ValueError:
            await update.message.reply_text("مقدار نامعتبر. دوباره بفرستید:")
            context.user_data["ord_edit_id"] = oid
            context.user_data["ord_edit_field"] = field
            return WAITING_USER_FIELD
        result = edit_sold_service(oid, **kwargs)
        if result.get("ok"):
            await update.message.reply_text(f"✅ سرویس #{oid} به‌روز شد و در پاسارگارد ثبت شد.", reply_markup=main_keyboard())
        else:
            await update.message.reply_text(f"❌ خطا: {result.get('error')}", reply_markup=main_keyboard())
        return ConversationHandler.END

    # ---- ایموجی پریمیوم ----
    if context.user_data.get("premiji_step") == "code":
        from db_extras import gen_premium_code, add_premium_emoji
        code = text if text.startswith("p_") else (gen_premium_code() if not text else None)
        if not code or not code.startswith("p_"):
            await update.message.reply_text("کد باید با p_ شروع شود. دوباره:")
            return WAITING_USER_FIELD
        context.user_data["premiji_code"] = code
        context.user_data["premiji_step"] = "emoji"
        await update.message.reply_text(
            f"کد: <code>{code}</code>\n\nحالا یک پیام با ایموجی پریمیوم (کاستوم) بفرستید.",
            parse_mode="HTML",
        )
        return WAITING_USER_FIELD

    if context.user_data.get("premiji_step") == "emoji":
        from db_extras import add_premium_emoji
        code = context.user_data.get("premiji_code")
        # استخراج custom_emoji_id از entities
        entities = update.message.entities or []
        emoji_id = None
        for ent in entities:
            if getattr(ent, "type", None) == "custom_emoji":
                emoji_id = str(getattr(ent, "custom_emoji_id", "") or "")
                break
        if not emoji_id:
            # ممکن است فقط عدد فرستاده شود
            if text.isdigit():
                emoji_id = text
            else:
                await update.message.reply_text("ایموجی پریمیوم یافت نشد. یک پیام با ایموجی کاستوم بفرستید یا شناسه عددی:")
                return WAITING_USER_FIELD
        ok = add_premium_emoji(code, emoji_id, created_by=user.id)
        context.user_data.pop("premiji_step", None)
        context.user_data.pop("premiji_code", None)
        if ok:
            await update.message.reply_text(
                f"✅ ثبت شد.\nکد: <code>{code}</code>\nID: <code>{emoji_id}</code>\n\n"
                f"هر جا از <code>{code}</code> استفاده کنید با parse_mode=HTML به ایموجی پریمیوم تبدیل می‌شود.",
                reply_markup=main_keyboard(),
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text("❌ خطا در ثبت.", reply_markup=main_keyboard())
        return ConversationHandler.END

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
