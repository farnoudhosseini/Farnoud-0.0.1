# پنل مدیریت وب فرنود

from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from config import SECRET_KEY
from database import (
    check_admin, get_setting_sync, set_setting_sync, ensure_tables_sync,
    list_panels, get_panel_by_id, get_panel_by_slug, create_panel,
    update_panel_status, delete_panel,
)
from db_products import (
    ensure_product_tables, list_categories, add_category, update_category, delete_category,
    list_products, get_product, create_product, update_product, delete_product, move_product,
    ROLE_OPTIONS as PRODUCT_ROLES,
)
from db_support import (
    ensure_support_tables, list_departments, add_department, delete_department,
    list_open_tickets, get_ticket, get_ticket_messages, add_ticket_message, close_ticket,
)
from db_stats import dashboard_counts, chart_series
from services.pasarguard import PasarGuardClient, normalize_base_url, bytes_to_gb
from db_users import (
    ensure_user_tables, list_bot_users, get_bot_user, update_bot_user, add_balance,
    ROLE_LABELS, get_user_activity, count_referrals, list_templates, set_template,
    list_cards, add_card, delete_card, toggle_card, list_gift_codes, create_gift_code,
    list_pending_charges, approve_charge, reject_charge,
)


app = Flask(__name__)
app.secret_key = SECRET_KEY

try:
    ensure_tables_sync()
    ensure_user_tables()
    ensure_product_tables()
    ensure_support_tables()
except Exception:
    pass


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def get_client_for_panel(panel) -> PasarGuardClient:
    return PasarGuardClient(panel["base_url"], panel["username"], panel["password"], verify_ssl=False)


@app.route("/")
def index():
    if "admin_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "admin_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if not username or not password:
            flash("نام کاربری و رمز عبور الزامی است", "error")
            return render_template("login.html")
        admin = check_admin(username, password)
        if admin:
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]
            flash("با موفقیت وارد شدید", "success")
            return redirect(url_for("dashboard"))
        flash("نام کاربری یا رمز عبور اشتباه است", "error")
    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    stats = {}
    try:
        stats = dashboard_counts()
    except Exception as e:
        print("dashboard stats", e)
        stats = {}
    return render_template(
        "dashboard.html",
        username=session.get("admin_username"),
        active="dashboard",
        stats=stats,
    )

@app.route("/api/dashboard/chart")
@login_required
def api_dashboard_chart():
    period = request.args.get("period", "7")
    if period not in ("today", "7", "28", "all"):
        period = "7"
    try:
        data = chart_series(period)
        return jsonify({"ok": True, **data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "labels": [], "users": [], "orders": [], "revenue": []})



@app.route("/bot-messages", methods=["GET", "POST"])
@login_required
def bot_messages():
    if request.method == "POST":
        welcome = request.form.get("welcome_message", "").strip()
        if not welcome:
            flash("پیام خوش‌آمدگویی نمی‌تواند خالی باشد", "error")
        elif set_setting_sync("welcome_message", welcome):
            flash("پیام خوش‌آمدگویی ذخیره شد", "success")
        else:
            flash("خطا در ذخیره پیام", "error")
        return redirect(url_for("bot_messages"))
    return render_template(
        "bot_messages.html",
        username=session.get("admin_username"),
        active="bot_messages",
        welcome_message=get_setting_sync("welcome_message", "سلام! به ربات فرنود خوش آمدید 👋"),
    )


@app.route("/panels")
@login_required
def panels_list():
    return render_template("panels.html", username=session.get("admin_username"), active="panels", panels=list_panels())


@app.route("/panels/add", methods=["GET", "POST"])
@login_required
def panels_add():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        panel_type = request.form.get("panel_type", "pasarguard").strip()
        raw_url = request.form.get("panel_url", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if panel_type != "pasarguard":
            flash("فعلاً فقط پاسارگارد پشتیبانی می‌شود", "error")
            return render_template("panel_add.html", username=session.get("admin_username"), active="panels")
        if not all([name, raw_url, username, password]):
            flash("تمام فیلدها الزامی هستند", "error")
            return render_template("panel_add.html", username=session.get("admin_username"), active="panels")
        try:
            base_url = normalize_base_url(raw_url)
            client = PasarGuardClient(base_url, username, password, verify_ssl=False)
            client.test_connection()
        except Exception as e:
            flash(f"اتصال ناموفق: {e}", "error")
            return render_template("panel_add.html", username=session.get("admin_username"), active="panels")
        panel_id, slug = create_panel(name, panel_type, base_url, username, password)
        if not panel_id:
            flash("خطا در ذخیره پنل", "error")
            return render_template("panel_add.html", username=session.get("admin_username"), active="panels")
        flash(f"پنل «{name}» متصل شد", "success")
        return redirect(url_for("panel_detail", slug=slug))
    return render_template("panel_add.html", username=session.get("admin_username"), active="panels")


@app.route("/panels/<slug>")
@login_required
def panel_detail(slug):
    panel = get_panel_by_slug(slug)
    if not panel:
        flash("پنل یافت نشد", "error")
        return redirect(url_for("panels_list"))
    stats, error = None, None
    try:
        stats = get_client_for_panel(panel).get_system_stats()
        update_panel_status(panel["id"], "online")
    except Exception as e:
        error = str(e)
        update_panel_status(panel["id"], "offline")
    return render_template(
        "panel_detail.html",
        username=session.get("admin_username"), active="panels",
        panel=panel, stats=stats, error=error,
    )


@app.route("/api/panels/<slug>/stats")
@login_required
def panel_stats_api(slug):
    """JSON آمار برای رفرش هر ۵ ثانیه"""
    panel = get_panel_by_slug(slug)
    if not panel:
        return jsonify({"ok": False, "error": "پنل یافت نشد"}), 404
    try:
        stats = get_client_for_panel(panel).get_system_stats()
        update_panel_status(panel["id"], "online")
        return jsonify({"ok": True, "status": "online", "stats": stats})
    except Exception as e:
        update_panel_status(panel["id"], "offline")
        return jsonify({"ok": False, "status": "offline", "error": str(e)})


@app.route("/panels/<int:panel_id>/delete", methods=["POST"])
@login_required
def panels_delete(panel_id):
    ok = delete_panel(panel_id)
    flash("پنل حذف شد" if ok else "حذف ناموفق", "success" if ok else "error")
    return redirect(url_for("panels_list"))


# ---------- کاربران پنل VPN (کلاینت‌های پاسارگارد) ----------

@app.route("/panels/<slug>/users")
@login_required
def panel_users(slug):
    panel = get_panel_by_slug(slug)
    if not panel:
        flash("پنل یافت نشد", "error")
        return redirect(url_for("panels_list"))
    users, total, error = [], 0, None
    try:
        data = get_client_for_panel(panel).get_users(offset=0, limit=100)
        users = data.get("users") or []
        total = data.get("total", len(users))
    except Exception as e:
        error = str(e)
    return render_template(
        "panel_users.html",
        username=session.get("admin_username"), active="panels",
        panel=panel, users=users, total=total, error=error, bytes_to_gb=bytes_to_gb,
    )


@app.route("/panels/<slug>/users/add", methods=["GET", "POST"])
@login_required
def panel_user_add(slug):
    panel = get_panel_by_slug(slug)
    if not panel:
        flash("پنل یافت نشد", "error")
        return redirect(url_for("panels_list"))
    client = get_client_for_panel(panel)
    groups, groups_error = [], None
    try:
        groups = client.get_groups()
    except Exception as e:
        groups_error = str(e)

    if request.method == "POST":
        try:
            gids = request.form.getlist("group_ids")
            gids = [int(x) for x in gids if str(x).isdigit()]
            payload = client.build_user_payload(
                username=request.form.get("username", "").strip(),
                status=request.form.get("status", "active"),
                data_limit_gb=request.form.get("data_limit_gb") or 0,
                expire=request.form.get("expire") or None,
                group_ids=gids,
                hwid_limit=request.form.get("hwid_limit") or None,
                note=request.form.get("note") or None,
                on_hold_expire_duration=request.form.get("on_hold_days") or None,
                for_create=True,
            )
            # on_hold_days از فرم به ثانیه
            if payload.get("status") == "on_hold" and request.form.get("on_hold_days"):
                try:
                    payload["on_hold_expire_duration"] = int(float(request.form.get("on_hold_days")) * 86400)
                except ValueError:
                    pass
            user = client.create_user(payload)
            flash(f"کاربر «{user.get('username', payload['username'])}» ساخته شد", "success")
            return redirect(url_for("panel_users", slug=slug))
        except Exception as e:
            flash(f"خطا در ساخت کاربر: {e}", "error")

    return render_template(
        "panel_user_form.html",
        username=session.get("admin_username"), active="panels",
        panel=panel, groups=groups, groups_error=groups_error,
        mode="add", user=None,
    )


@app.route("/panels/<slug>/users/<vpn_username>/edit", methods=["GET", "POST"])
@login_required
def panel_user_edit(slug, vpn_username):
    panel = get_panel_by_slug(slug)
    if not panel:
        flash("پنل یافت نشد", "error")
        return redirect(url_for("panels_list"))
    client = get_client_for_panel(panel)
    groups = []
    try:
        groups = client.get_groups()
    except Exception:
        pass
    user = None
    try:
        user = client.get_user(vpn_username)
    except Exception as e:
        flash(f"کاربر یافت نشد: {e}", "error")
        return redirect(url_for("panel_users", slug=slug))

    if request.method == "POST":
        try:
            gids = request.form.getlist("group_ids")
            gids = [int(x) for x in gids if str(x).isdigit()]
            payload = client.build_user_payload(
                status=request.form.get("status", "active"),
                data_limit_gb=request.form.get("data_limit_gb"),
                expire=request.form.get("expire") or None,
                group_ids=gids,
                hwid_limit=request.form.get("hwid_limit") or None,
                note=request.form.get("note") or None,
                on_hold_expire_duration=request.form.get("on_hold_days") or None,
                for_create=False,
            )
            if payload.get("status") == "on_hold" and request.form.get("on_hold_days"):
                try:
                    payload["on_hold_expire_duration"] = int(float(request.form.get("on_hold_days")) * 86400)
                except ValueError:
                    pass
            # اگر تاریخ خالی بود برای نامحدود
            if not request.form.get("expire"):
                payload["expire"] = None
            client.modify_user(vpn_username, payload)
            flash("اطلاعات کاربر به‌روز شد", "success")
            return redirect(url_for("panel_users", slug=slug))
        except Exception as e:
            flash(f"خطا در ویرایش: {e}", "error")

    return render_template(
        "panel_user_form.html",
        username=session.get("admin_username"), active="panels",
        panel=panel, groups=groups, groups_error=None,
        mode="edit", user=user, bytes_to_gb=bytes_to_gb,
    )


@app.route("/panels/<slug>/users/<vpn_username>/delete", methods=["POST"])
@login_required
def panel_user_delete(slug, vpn_username):
    panel = get_panel_by_slug(slug)
    if not panel:
        flash("پنل یافت نشد", "error")
        return redirect(url_for("panels_list"))
    try:
        get_client_for_panel(panel).delete_user(vpn_username)
        flash(f"کاربر «{vpn_username}» حذف شد", "success")
    except Exception as e:
        flash(f"خطا در حذف: {e}", "error")
    return redirect(url_for("panel_users", slug=slug))




# ---------- کاربران ربات ----------
@app.route("/users")
@login_required
def bot_users_list():
    q = request.args.get("q", "").strip() or None
    users, total = list_bot_users(limit=100, search=q)
    return render_template(
        "bot_users.html",
        username=session.get("admin_username"), active="bot_users",
        users=users, total=total, q=q or "", roles=ROLE_LABELS,
    )

@app.route("/users/<int:telegram_id>", methods=["GET", "POST"])
@login_required
def bot_user_detail(telegram_id):
    user = get_bot_user(telegram_id)
    if not user:
        flash("کاربر یافت نشد", "error")
        return redirect(url_for("bot_users_list"))
    if request.method == "POST":
        action = request.form.get("action")
        if action == "save":
            update_bot_user(
                telegram_id,
                phone=request.form.get("phone") or None,
                role=request.form.get("role") or "user",
                is_blocked=1 if request.form.get("is_blocked") == "1" else 0,
            )
            flash("ذخیره شد", "success")
        elif action == "add_balance":
            try:
                amt = int(request.form.get("amount", "0"))
                if amt != 0:
                    add_balance(telegram_id, amt, "admin_web")
                    flash(f"موجودی تغییر کرد: {amt:+,}", "success")
            except ValueError:
                flash("مبلغ نامعتبر", "error")
        return redirect(url_for("bot_user_detail", telegram_id=telegram_id))
    activity = get_user_activity(telegram_id, 40)
    refs = count_referrals(telegram_id)
    return render_template(
        "bot_user_detail.html",
        username=session.get("admin_username"), active="bot_users",
        user=user, activity=activity, refs=refs, roles=ROLE_LABELS,
    )

# ---------- پیام‌ها و کیف پول تنظیمات ----------
@app.route("/messages", methods=["GET", "POST"])
@login_required
def messages_manage():
    if request.method == "POST":
        key = request.form.get("key")
        body = request.form.get("body", "")
        if key:
            set_template(key, body)
            flash("پیام ذخیره شد", "success")
        if request.form.get("min_charge"):
            set_setting_sync("min_charge", request.form.get("min_charge"))
        if request.form.get("max_charge"):
            set_setting_sync("max_charge", request.form.get("max_charge"))
        return redirect(url_for("messages_manage"))
    templates = list_templates()
    return render_template(
        "messages.html",
        username=session.get("admin_username"), active="messages",
        templates=templates,
        min_charge=get_setting_sync("min_charge", "10000"),
        max_charge=get_setting_sync("max_charge", "50000000"),
    )

# ---------- کارت‌ها ----------
@app.route("/cards", methods=["GET", "POST"])
@login_required
def cards_manage():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            add_card(
                request.form.get("card_number", "").strip(),
                request.form.get("owner_name", "").strip(),
                request.form.get("bank_name") or None,
            )
            flash("کارت اضافه شد", "success")
        elif action == "delete":
            delete_card(int(request.form.get("card_id")))
            flash("حذف شد", "success")
        elif action == "toggle":
            toggle_card(int(request.form.get("card_id")), request.form.get("active") == "1")
        return redirect(url_for("cards_manage"))
    return render_template(
        "cards.html",
        username=session.get("admin_username"), active="cards",
        cards=list_cards(),
    )

@app.route("/charges")
@login_required
def charges_list():
    pending = list_pending_charges()
    return render_template(
        "charges.html",
        username=session.get("admin_username"), active="charges",
        pending=pending,
    )

@app.route("/charges/<int:cid>/approve", methods=["POST"])
@login_required
def charge_approve(cid):
    if approve_charge(cid):
        flash("تایید شد", "success")
    else:
        flash("ناموفق", "error")
    return redirect(url_for("charges_list"))

@app.route("/charges/<int:cid>/reject", methods=["POST"])
@login_required
def charge_reject(cid):
    reject_charge(cid, request.form.get("reason") or "رد شده")
    flash("رد شد", "success")
    return redirect(url_for("charges_list"))

@app.route("/gifts", methods=["GET", "POST"])
@login_required
def gifts_manage():
    if request.method == "POST":
        ok = create_gift_code(
            request.form.get("code", ""),
            int(request.form.get("amount") or 0),
            int(request.form.get("max_uses") or 1),
        )
        flash("کد ساخته شد" if ok else "خطا (شاید کد تکراری)", "success" if ok else "error")
        return redirect(url_for("gifts_manage"))
    return render_template(
        "gifts.html",
        username=session.get("admin_username"), active="gifts",
        codes=list_gift_codes(),
    )



# ---------- محصولات ----------
@app.route("/products")
@login_required
def products_list():
    return render_template(
        "products.html",
        username=session.get("admin_username"), active="products",
        products=list_products(), roles=PRODUCT_ROLES,
    )

@app.route("/products/add", methods=["GET", "POST"])
@login_required
def products_add():
    from database import list_panels
    panels = list_panels()
    cats = list_categories()
    if request.method == "POST":
        panel_ids = request.form.getlist("panel_ids")
        cat = request.form.get("category_id") or None
        create_product(
            name=request.form.get("name", "").strip(),
            price=int(request.form.get("price") or 0),
            volume_gb=float(request.form.get("volume_gb") or 0),
            duration_days=int(request.form.get("duration_days") or 30),
            target_role=request.form.get("target_role") or "all",
            category_id=int(cat) if cat else None,
            description=request.form.get("description") or None,
            panel_ids=panel_ids,
        )
        flash("محصول اضافه شد", "success")
        return redirect(url_for("products_list"))
    return render_template(
        "product_form.html",
        username=session.get("admin_username"), active="products",
        mode="add", product=None, panels=panels, categories=cats, roles=PRODUCT_ROLES,
    )

@app.route("/products/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def products_edit(pid):
    from database import list_panels
    product = get_product(pid)
    if not product:
        flash("یافت نشد", "error")
        return redirect(url_for("products_list"))
    panels = list_panels()
    cats = list_categories()
    if request.method == "POST":
        cat = request.form.get("category_id") or None
        update_product(
            pid,
            panel_ids=request.form.getlist("panel_ids"),
            name=request.form.get("name", "").strip(),
            price=int(request.form.get("price") or 0),
            volume_gb=float(request.form.get("volume_gb") or 0),
            duration_days=int(request.form.get("duration_days") or 30),
            target_role=request.form.get("target_role") or "all",
            category_id=int(cat) if cat else None,
            description=request.form.get("description") or None,
            is_active=1 if request.form.get("is_active") == "1" else 0,
        )
        flash("ذخیره شد", "success")
        return redirect(url_for("products_list"))
    return render_template(
        "product_form.html",
        username=session.get("admin_username"), active="products",
        mode="edit", product=product, panels=panels, categories=cats, roles=PRODUCT_ROLES,
    )

@app.route("/products/<int:pid>/delete", methods=["POST"])
@login_required
def products_delete(pid):
    delete_product(pid)
    flash("حذف شد", "success")
    return redirect(url_for("products_list"))

@app.route("/products/<int:pid>/move/<direction>", methods=["POST"])
@login_required
def products_move(pid, direction):
    move_product(pid, direction)
    return redirect(url_for("products_list"))

@app.route("/categories", methods=["GET", "POST"])
@login_required
def categories_list():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            add_category(request.form.get("name", "").strip())
            flash("دسته اضافه شد", "success")
        elif action == "delete":
            delete_category(int(request.form.get("cid")))
            flash("حذف شد", "success")
        return redirect(url_for("categories_list"))
    return render_template(
        "categories.html",
        username=session.get("admin_username"), active="categories",
        categories=list_categories(),
    )



@app.route("/support/departments", methods=["GET", "POST"])
@login_required
def support_departments():
    if request.method == "POST":
        if request.form.get("action") == "add":
            add_department(request.form.get("name", "").strip(), request.form.get("description"))
            flash("دپارتمان اضافه شد", "success")
        elif request.form.get("action") == "delete":
            delete_department(int(request.form.get("did")))
            flash("حذف شد", "success")
        return redirect(url_for("support_departments"))
    return render_template(
        "support_deps.html",
        username=session.get("admin_username"), active="support",
        departments=list_departments(active_only=False),
    )

@app.route("/support/tickets")
@login_required
def support_tickets():
    return render_template(
        "support_tickets.html",
        username=session.get("admin_username"), active="support",
        tickets=list_open_tickets(),
    )

@app.route("/support/tickets/<int:tid>", methods=["GET", "POST"])
@login_required
def support_ticket_detail(tid):
    t = get_ticket(tid)
    if not t:
        flash("تیکت نیست", "error")
        return redirect(url_for("support_tickets"))
    if request.method == "POST":
        msg = request.form.get("message", "").strip()
        if msg:
            add_ticket_message(tid, "admin", msg)
            flash("پاسخ ثبت شد", "success")
        if request.form.get("close"):
            close_ticket(tid)
            flash("بسته شد", "success")
        return redirect(url_for("support_ticket_detail", tid=tid))
    return render_template(
        "support_ticket_detail.html",
        username=session.get("admin_username"), active="support",
        ticket=t, messages=get_ticket_messages(tid),
    )


@app.route("/personalize")
@login_required
def personalize():
    return render_template("personalize.html", username=session.get("admin_username"), active="personalize")


@app.route("/logout")
def logout():
    session.clear()
    flash("با موفقیت خارج شدید", "success")
    return redirect(url_for("login"))


if __name__ == "__main__":
    print("🌐 پنل مدیریت فرنود در حال اجرا روی http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
