# پنل مدیریت وب فرنود

from functools import wraps
from werkzeug.middleware.proxy_fix import ProxyFix
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
    list_all_orders, get_order_full, ensure_service_mgmt_columns, reorder_products,
    ROLE_OPTIONS as PRODUCT_ROLES,
)
from db_support import (
    ensure_support_tables, list_departments, add_department, delete_department,
    list_open_tickets, get_ticket, get_ticket_messages, add_ticket_message, close_ticket,
)
from db_stats import dashboard_counts, chart_series
from db_growth import (
    ensure_growth_tables, list_discounts, create_discount,
    list_reseller_requests, review_reseller_request, get_reseller_request,
)
from database import list_panels as db_list_panels
from services.pasarguard import PasarGuardClient, normalize_base_url, bytes_to_gb
from db_users import (
    ensure_user_tables, list_bot_users, get_bot_user, update_bot_user, add_balance,
    ROLE_LABELS, get_user_activity, count_referrals, list_templates, set_template,
    list_cards, add_card, delete_card, toggle_card, list_gift_codes, create_gift_code,
    list_pending_charges, approve_charge, reject_charge, render_template as render_msg_template,
)


app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.secret_key = SECRET_KEY

# Telegram Mini App: public API routes are isolated in a Blueprint and use Telegram initData auth.
try:
    from miniapp import miniapp_bp
    app.register_blueprint(miniapp_bp)
except Exception as _miniapp_import_error:
    print('Mini App registration warning:', _miniapp_import_error)

try:
    ensure_tables_sync()
    ensure_user_tables()
    ensure_product_tables()
    ensure_support_tables()
    ensure_growth_tables()
    ensure_service_mgmt_columns()
    from db_extras import ensure_extras_tables
    ensure_extras_tables()
except Exception:
    pass


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def get_client_for_panel(panel):
    from services.panel_client import get_panel_client
    return get_panel_client(panel)


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
    return redirect(url_for("messages_manage"))


@app.route("/panels")
@login_required
def panels_list():
    return render_template("panels.html", username=session.get("admin_username"), active="panels", panels=list_panels())


@app.route("/panels/add", methods=["GET", "POST"])
@login_required
def panels_add():
    try:
        from database import ensure_panel_max_sales
        ensure_panel_max_sales()
    except Exception:
        pass
    selected_type = (request.args.get("type") or request.form.get("panel_type") or "").strip().lower()
    if selected_type in ("3xui", "xui", "sanaei"):
        selected_type = "3x-ui"
    if selected_type not in ("", "pasarguard", "3x-ui"):
        selected_type = ""

    if request.method == "GET":
        return render_template(
            "panel_add.html",
            username=session.get("admin_username"),
            active="panels",
            selected_type=selected_type or None,
        )

    name = request.form.get("name", "").strip()
    panel_type = (request.form.get("panel_type") or "").strip().lower()
    if panel_type in ("3xui", "xui", "sanaei"):
        panel_type = "3x-ui"
    raw_url = request.form.get("panel_url", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    api_key = (request.form.get("api_key") or "").strip()
    auth_mode = (request.form.get("auth_mode") or "").strip()

    def _form(ptype):
        return render_template(
            "panel_add.html",
            username=session.get("admin_username"),
            active="panels",
            selected_type=ptype,
        )

    if panel_type not in ("pasarguard", "3x-ui"):
        flash("نوع پنل را انتخاب کنید", "error")
        return redirect(url_for("panels_add"))
    if not name or not raw_url:
        flash("نام و آدرس الزامی است", "error")
        return _form(panel_type)

    try:
        if panel_type == "pasarguard":
            if not username or not password:
                flash("برای پاسارگارد یوزر و رمز لازم است", "error")
                return _form("pasarguard")
            base_url = normalize_base_url(raw_url)
            client = PasarGuardClient(base_url, username, password, verify_ssl=False)
            client.test_connection()
            api_key = None
        else:
            from services.xui3 import XUI3Client, normalize_xui_base
            use_token = (auth_mode == "token") or bool(api_key)
            if use_token:
                if not api_key:
                    flash("API Token را وارد کنید", "error")
                    return _form("3x-ui")
                username, password = "", ""
            else:
                api_key = ""
                if not username or not password:
                    flash("نام کاربری و رمز عبور لازم است", "error")
                    return _form("3x-ui")
            base_url = normalize_xui_base(raw_url)
            client = XUI3Client(
                base_url,
                username=username,
                password=password,
                api_token=api_key,
                verify_ssl=False,
            )
            client.test_connection()
    except Exception as e:
        flash(f"اتصال ناموفق: {e}", "error")
        return _form(panel_type)

    panel_id, slug_or_err = create_panel(
        name,
        panel_type,
        base_url,
        username or ("token" if api_key else "admin"),
        password or "",
        api_key=api_key or None,
    )
    if not panel_id:
        flash(f"خطا در ذخیره پنل: {slug_or_err}", "error")
        return _form(panel_type)
    slug = slug_or_err

    try:
        ms = (request.form.get("max_sales") or "").strip()
        if ms != "":
            from database import set_panel_max_sales
            set_panel_max_sales(panel_id, int(ms) if int(ms) > 0 else None)
    except Exception:
        pass

    flash(f"پنل «{name}» ({panel_type}) متصل شد", "success")
    return redirect(url_for("panel_detail", slug=slug))


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

@app.route("/bot/settings", methods=["GET", "POST"])
@login_required
def bot_settings():
    if request.method == "POST":
        if "welcome_message" in request.form:
            set_setting_sync("welcome_message", request.form.get("welcome_message", "").strip())
        if request.form.get("backup_interval_hours") is not None:
            try:
                _bh = max(1, min(int(float(request.form.get("backup_interval_hours") or 2)), 168))
                set_setting_sync("backup_interval_hours", str(_bh))
            except Exception:
                flash("فاصله بکاپ نامعتبر", "error")
        flash("ذخیره شد", "success")
        return redirect(url_for("bot_settings"))
    return render_template(
        "bot_settings.html",
        username=session.get("admin_username"),
        active="bot_settings",
        welcome_message=get_setting_sync("welcome_message", "سلام! به ربات فرنود خوش آمدید 👋"),
        backup_interval_hours=get_setting_sync("backup_interval_hours", "2"),
    )

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
        if "welcome_message" in request.form:
            set_setting_sync("welcome_message", request.form.get("welcome_message", "").strip())
        return redirect(url_for("messages_manage"))
    templates = list_templates()
    return render_template(
        "messages.html",
        username=session.get("admin_username"), active="messages",
        templates=templates,
        min_charge=get_setting_sync("min_charge", "10000"),
        max_charge=get_setting_sync("max_charge", "50000000"),
        welcome_message=get_setting_sync("welcome_message", "سلام! به ربات فرنود خوش آمدید 👋"),
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

def _parse_panel_config_from_form(panel_ids):
    """از فرم: panel_groups_{id} / panel_inbounds_{id}"""
    cfg = {}
    for pid in panel_ids:
        pid = int(pid)
        groups = request.form.getlist(f"panel_groups_{pid}")
        inbounds = request.form.getlist(f"panel_inbounds_{pid}")
        entry = {}
        if groups:
            entry["group_ids"] = [int(x) for x in groups if str(x).isdigit()]
        if inbounds:
            entry["inbound_ids"] = [int(x) for x in inbounds if str(x).isdigit()]
        if entry:
            cfg[pid] = entry
    return cfg


@app.route("/api/panels/<int:panel_id>/groups")
@login_required
def api_panel_groups(panel_id):
    from database import get_panel_by_id
    panel = get_panel_by_id(panel_id)
    if not panel:
        return jsonify({"ok": False, "error": "پنل یافت نشد"}), 404
    try:
        client = get_client_for_panel(panel)
        groups = client.get_groups() if hasattr(client, "get_groups") else []
        items = []
        for g in groups or []:
            items.append({
                "id": g.get("id"),
                "label": g.get("name") or g.get("title") or str(g.get("id")),
            })
        return jsonify({"ok": True, "items": items})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/panels/<int:panel_id>/inbounds")
@login_required
def api_panel_inbounds(panel_id):
    from database import get_panel_by_id
    panel = get_panel_by_id(panel_id)
    if not panel:
        return jsonify({"ok": False, "error": "پنل یافت نشد"}), 404
    try:
        client = get_client_for_panel(panel)
        if not hasattr(client, "list_inbound_choices"):
            return jsonify({"ok": False, "error": "این پنل اینباند ندارد"})
        choices = client.list_inbound_choices()
        items = []
        for ib in choices or []:
            items.append({
                "id": ib.get("id"),
                "label": f"{ib.get('remark') or ib.get('id')} ({ib.get('protocol')}:{ib.get('port')})",
            })
        return jsonify({"ok": True, "items": items})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/products")
@login_required
def products_list():
    return render_template(
        "products.html",
        username=session.get("admin_username"), active="products",
        products=list_products(), roles=PRODUCT_ROLES,
    )

def _parse_hwid_limit(raw):
    """خالی یا نامعتبر = None (نامحدود)"""
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "":
        return None
    try:
        v = int(s)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


@app.route("/products/add", methods=["GET", "POST"])
@login_required
def products_add():
    from database import list_panels
    panels = list_panels()
    cats = list_categories()
    if request.method == "POST":
        panel_ids = request.form.getlist("panel_ids")
        pcfg = _parse_panel_config_from_form(panel_ids)
        cat = request.form.get("category_id") or None
        pid = create_product(
            name=request.form.get("name", "").strip(),
            price=int(request.form.get("price") or 0),
            volume_gb=float(request.form.get("volume_gb") or 0),
            duration_days=int(request.form.get("duration_days") or 30),
            hwid_limit=_parse_hwid_limit(request.form.get("hwid_limit")),
            target_role=request.form.get("target_role") or "all",
            category_id=int(cat) if cat else None,
            description=request.form.get("description") or None,
            panel_ids=panel_ids,
            panel_config=pcfg,
        )
        update_product(
            pid,
            hourly_enabled=1 if request.form.get("hourly_enabled") == "1" else 0,
            hourly_price=float(request.form.get("hourly_price") or 0) or None,
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
        pids = request.form.getlist("panel_ids")
        pcfg = _parse_panel_config_from_form(pids)
        update_product(
            pid,
            panel_ids=pids,
            panel_config=pcfg,
            name=request.form.get("name", "").strip(),
            price=int(request.form.get("price") or 0),
            volume_gb=float(request.form.get("volume_gb") or 0),
            duration_days=int(request.form.get("duration_days") or 30),
            hwid_limit=_parse_hwid_limit(request.form.get("hwid_limit")),
            target_role=request.form.get("target_role") or "all",
            category_id=int(cat) if cat else None,
            description=request.form.get("description") or None,
            is_active=1 if request.form.get("is_active") == "1" else 0,
            hourly_enabled=1 if request.form.get("hourly_enabled") == "1" else 0,
            hourly_price=float(request.form.get("hourly_price") or 0) or None,
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

@app.route("/api/products/reorder", methods=["POST"])
@login_required
def products_reorder_api():
    payload = request.get_json(silent=True) or {}
    ok = reorder_products(payload.get("ids") or [])
    return jsonify({"ok": ok})

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



@app.route("/growth", methods=["GET", "POST"])
@login_required
def growth_settings():
    """احراز هویت، تست رایگان، لوکیشن، تخفیف — بدون رفرال"""
    if request.method == "POST":
        action = request.form.get("action")
        if action == "settings":
            for key in [
                "force_join_enabled", "force_join_channel", "force_phone_enabled",
                "trial_enabled", "trial_panel_id", "trial_volume_gb", "trial_days",
                "location_change_enabled", "location_change_price", "location_change_limit",
            ]:
                val = request.form.get(key)
                if key.endswith("_enabled"):
                    val = "1" if request.form.get(key) == "1" else "0"
                elif val is None:
                    continue
                set_setting_sync(key, val)
            flash("تنظیمات ذخیره شد", "success")
        elif action == "discount":
            ok = create_discount(
                request.form.get("code", ""),
                percent=float(request.form.get("percent") or 0) or None,
                amount=int(request.form.get("amount") or 0) or None,
                max_uses=int(request.form.get("max_uses") or 0),
            )
            flash("کد ساخته شد" if ok else "خطا", "success" if ok else "error")
        return redirect(url_for("growth_settings"))
    return render_template(
        "growth.html",
        username=session.get("admin_username"), active="growth",
        panels=list_panels(),
        discounts=list_discounts(),
        s={
            "force_join_enabled": get_setting_sync("force_join_enabled", "0"),
            "force_join_channel": get_setting_sync("force_join_channel", ""),
            "force_phone_enabled": get_setting_sync("force_phone_enabled", "0"),
            "trial_enabled": get_setting_sync("trial_enabled", "0"),
            "trial_panel_id": get_setting_sync("trial_panel_id", ""),
            "trial_volume_gb": get_setting_sync("trial_volume_gb", "1"),
            "trial_days": get_setting_sync("trial_days", "1"),
            "location_change_enabled": get_setting_sync("location_change_enabled", "1"),
            "location_change_price": get_setting_sync("location_change_price", "0"),
            "location_change_limit": get_setting_sync("location_change_limit", "3"),
        },
    )


@app.route("/referral", methods=["GET", "POST"])
@login_required
def referral_settings():
    """سیستم رفرال — جدا از احراز هویت"""
    if request.method == "POST":
        set_setting_sync(
            "referral_enabled",
            "1" if request.form.get("referral_enabled") == "1" else "0",
        )
        set_setting_sync("referral_percent", request.form.get("referral_percent") or "10")
        set_setting_sync("referral_min_amount", request.form.get("referral_min_amount") or "0")
        set_setting_sync("referral_signup_bonus", request.form.get("referral_signup_bonus") or "0")
        set_setting_sync("referral_monthly_cap", request.form.get("referral_monthly_cap") or "0")
        set_setting_sync("referral_notify", "1" if request.form.get("referral_notify") == "1" else "0")
        flash("تنظیمات رفرال ذخیره شد", "success")
        return redirect(url_for("referral_settings"))
    return render_template(
        "referral.html",
        username=session.get("admin_username"), active="referral",
        s={
            "referral_enabled": get_setting_sync("referral_enabled", "1"),
            "referral_percent": get_setting_sync("referral_percent", "10"),
            "referral_min_amount": get_setting_sync("referral_min_amount", "0"),
            "referral_signup_bonus": get_setting_sync("referral_signup_bonus", "0"),
            "referral_monthly_cap": get_setting_sync("referral_monthly_cap", "0"),
            "referral_notify": get_setting_sync("referral_notify", "1"),
        },
    )


@app.route("/reseller-requests", methods=["GET", "POST"])
@login_required
def reseller_requests_page():
    """تایید/رد درخواست نمایندگی — فقط از وب‌پنل"""
    if request.method == "POST":
        action = request.form.get("action")
        if action == "settings":
            set_setting_sync(
                "reseller_request_enabled",
                "1" if request.form.get("reseller_request_enabled") == "1" else "0",
            )
            flash("ذخیره شد", "success")
        elif action == "review":
            rid = int(request.form.get("request_id") or 0)
            decision = request.form.get("decision")  # approved | rejected
            rtype = request.form.get("reseller_type") or "reseller"
            note = request.form.get("admin_note") or ""
            req = get_reseller_request(rid)
            ok = review_reseller_request(rid, decision, reseller_type=rtype, admin_note=note)
            if ok and req:
                try:
                    import requests as req_lib
                    from config import BOT_TOKEN
                    tg_id = req["telegram_id"]
                    if decision == "approved":
                        type_label = "نماینده ویژه" if rtype == "reseller_vip" else "نماینده عادی"
                        text = render_msg_template("reseller_approved", {
                            "reseller_type": type_label,
                        }) or f"🎉 درخواست نمایندگی تایید شد!\nنوع: {type_label}"
                    else:
                        text = render_msg_template("reseller_rejected", {
                            "reason": note or "—",
                        }) or f"❌ درخواست نمایندگی رد شد.\nدلیل: {note or '—'}"
                    try:
                        from db_extras import apply_premium_emojis
                        text = apply_premium_emojis(text)
                    except Exception:
                        pass
                    req_lib.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        json={"chat_id": tg_id, "text": text, "parse_mode": "HTML"},
                        timeout=10,
                    )
                except Exception as e:
                    print("notify reseller:", e)
                flash("انجام شد", "success")
            else:
                flash("خطا یا درخواست قبلاً بررسی شده", "error")
        return redirect(url_for("reseller_requests_page"))
    return render_template(
        "reseller_requests.html",
        username=session.get("admin_username"), active="reseller_requests",
        requests=list_reseller_requests(),
        reseller_enabled=get_setting_sync("reseller_request_enabled", "1"),
    )



@app.route("/orders")
@login_required
def orders_list():
    q = request.args.get("q") or None
    orders = list_all_orders(limit=100, search=q)
    return render_template(
        "orders.html",
        username=session.get("admin_username"), active="orders",
        orders=orders, q=q or "",
    )


@app.route("/orders/<int:oid>/edit", methods=["GET", "POST"])
@login_required
def order_edit(oid):
    order = get_order_full(oid)
    if not order:
        flash("یافت نشد", "error")
        return redirect(url_for("orders_list"))
    if request.method == "POST":
        from services.service_edit import edit_sold_service
        kwargs = {}
        vol = request.form.get("volume_gb", "").strip()
        days = request.form.get("duration_days", "").strip()
        hwid = request.form.get("hwid_limit", "").strip()
        status = request.form.get("status") or None
        note = request.form.get("admin_note")
        if vol != "":
            kwargs["volume_gb"] = float(vol)
        if days != "":
            kwargs["duration_days"] = int(days)
        if hwid != "":
            kwargs["hwid_limit"] = int(hwid)
        if status:
            kwargs["status"] = status
        if note is not None:
            kwargs["note"] = note
        result = edit_sold_service(oid, **kwargs)
        if result.get("ok"):
            flash("ذخیره و سینک شد", "success")
        else:
            flash(f"خطا: {result.get('error')}", "error")
        return redirect(url_for("order_edit", oid=oid))
    return render_template(
        "order_edit.html",
        username=session.get("admin_username"), active="orders",
        order=order,
    )


@app.route("/personalize")
@login_required
def personalize():
    return render_template("personalize.html", username=session.get("admin_username"), active="personalize")



@app.route("/menu-buttons", methods=["GET", "POST"])
@login_required
def menu_buttons_manage():
    from db_extras import get_menu_buttons, set_menu_buttons, DEFAULT_MENU_BUTTONS
    if request.method=="POST":
        data=request.get_json(silent=True) or {}
        if data.get("reset_default"):
            set_menu_buttons([dict(x) for x in DEFAULT_MENU_BUTTONS])
            if request.is_json:
                return jsonify({"ok": True})
            flash("چیدمان به پیش‌فرض برگشت", "success")
            return redirect(url_for("menu_buttons_manage"))
        if isinstance(data.get("items"), list):
            items = data["items"]
        else:
            import json
            try:
                items = json.loads(request.form.get("items", "[]"))
            except Exception:
                items = []
        clean = []
        allowed_colors = {"green", "red", "blue", "none", "primary", "success", "danger"}
        for i, x in enumerate(items):
            if not isinstance(x, dict):
                continue
            color = str(x.get("color") or "none").lower()
            if color not in allowed_colors:
                color = "none"
            try:
                row = int(x.get("row", i // 2))
            except Exception:
                row = i // 2
            try:
                col = int(x.get("col", i))
            except Exception:
                col = i
            clean.append({
                "key": str(x.get("key", ""))[:40] or f"btn_{i}",
                "label": str(x.get("label", ""))[:120],
                "callback": str(x.get("callback", "menu_home"))[:60],
                "enabled": bool(x.get("enabled", True)),
                "color": color,
                "row": row,
                "col": col,
            })
        set_menu_buttons(clean)
        if request.is_json:
            return jsonify({"ok": True})
        flash("چیدمان دکمه‌ها ذخیره شد", "success")
        return redirect(url_for("menu_buttons_manage"))
    return render_template(
        "menu_buttons.html",
        username=session.get("admin_username"),
        active="menu_buttons",
        items=get_menu_buttons(),
    )

@app.route("/premium-emojis", methods=["GET", "POST"])
@login_required
def premium_emojis_manage():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "save":
            code = (request.form.get("code") or "").strip()
            if not code:
                code = gen_premium_code()
            if not code.startswith("p_"):
                code = "p_" + code
            ok = add_premium_emoji(code, request.form.get("custom_emoji_id","").strip(),
                                   request.form.get("label","").strip() or None,
                                   session.get("admin_id"))
            flash("ایموجی پریمیوم ذخیره شد" if ok else "ذخیره ناموفق", "success" if ok else "error")
        elif action == "delete":
            delete_premium_emoji(request.form.get("code",""))
            flash("حذف شد", "success")
        return redirect(url_for("premium_emojis_manage"))
    return render_template("premium_emojis.html", username=session.get("admin_username"),
                           active="premium_emojis", emojis=list_premium_emojis())

@app.route("/panels/<int:panel_id>/settings", methods=["POST"])
@login_required
def panel_settings(panel_id):
    panel = get_panel_by_id(panel_id)
    if not panel:
        flash("پنل یافت نشد", "error")
        return redirect(url_for("panels_list"))
    from database import get_sync_connection
    renew_mode = (request.form.get("renew_mode") or "").strip()
    if renew_mode in ("reset_both", "reset_time", "reset_volume", "additive"):
        conn = get_sync_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE vpn_panels SET renew_mode=%s WHERE id=%s", (renew_mode, panel_id))
                conn.commit()
        finally:
            conn.close()
        flash("روش تمدید ذخیره شد", "success")
        return redirect(url_for("panel_detail", slug=panel["slug"]))
    raw = (request.form.get("max_sales") or "").strip()
    try:
        max_sales = int(raw) if raw else None
        if max_sales is not None and max_sales < 0:
            raise ValueError
    except ValueError:
        flash("سقف فروش نامعتبر است", "error")
        return redirect(url_for("panel_detail", slug=panel["slug"]))
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE vpn_panels SET max_sales=%s WHERE id=%s", (max_sales, panel_id))
            conn.commit()
    finally:
        conn.close()
    flash("سقف فروش پنل ذخیره شد", "success")
    return redirect(url_for("panel_detail", slug=panel["slug"]))




# ---------- Telegram Mini App content management ----------

@app.route("/miniapp-content")
@login_required
def miniapp_content():
    from database import get_sync_connection
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM news ORDER BY id DESC LIMIT 30")
            news = cur.fetchall() or []
            cur.execute("SELECT * FROM banners ORDER BY id DESC LIMIT 30")
            banners = cur.fetchall() or []
        return render_template("miniapp_content.html", username=session.get("admin_username"),
                               active="miniapp", news=news, banners=banners,
                               miniapp_url=get_setting_sync("miniapp_url", "") or "")
    finally:
        conn.close()



@app.route("/miniapp-content/settings", methods=["POST"])
@login_required
def miniapp_settings_save():
    url = (request.form.get("miniapp_url") or "").strip().rstrip("/")
    if url and not url.startswith("https://") and not url.startswith("http://"):
        url = "https://" + url
    if url and not url.endswith("/miniapp") and "/miniapp" not in url:
        url = url.rstrip("/") + "/miniapp/"
    elif url and not url.endswith("/"):
        url = url + "/"
    set_setting_sync("miniapp_url", url)
    flash("آدرس مینی‌اپ ذخیره شد", "success")
    return redirect(url_for("miniapp_content"))

@app.route("/miniapp-content/news", methods=["POST"])
@login_required
def miniapp_news_create():
    from database import get_sync_connection
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO news (title,summary,content,image_url,published_at,is_active)
                           VALUES (%s,%s,%s,%s,NOW(),1)""",
                        (request.form.get("title","").strip(),
                         request.form.get("summary","").strip(),
                         request.form.get("content","").strip(),
                         request.form.get("image_url","").strip() or None))
            conn.commit()
        flash("خبر منتشر شد", "success")
    except Exception as e:
        flash(f"خطا در انتشار خبر: {e}", "error")
    finally:
        conn.close()
    return redirect(url_for("miniapp_content"))


@app.route("/miniapp-content/banners", methods=["POST"])
@login_required
def miniapp_banner_create():
    from database import get_sync_connection
    conn = get_sync_connection()
    try:
        priority = int(request.form.get("priority") or 0)
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO banners
                           (title,description,image_url,cta,link,priority,is_active)
                           VALUES (%s,%s,%s,%s,%s,%s,1)""",
                        (request.form.get("title","").strip(),
                         request.form.get("description","").strip(),
                         request.form.get("image_url","").strip() or None,
                         request.form.get("cta","").strip() or None,
                         request.form.get("link","").strip() or None,
                         priority))
            conn.commit()
        flash("Banner ذخیره شد", "success")
    except Exception as e:
        flash(f"خطا در ذخیره Banner: {e}", "error")
    finally:
        conn.close()
    return redirect(url_for("miniapp_content"))


@app.route("/miniapp-content/notifications", methods=["POST"])
@login_required
def miniapp_notification_create():
    from database import get_sync_connection
    conn = get_sync_connection()
    try:
        raw_id = request.form.get("telegram_id","").strip()
        tg_id = int(raw_id) if raw_id else None
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO notifications
                           (telegram_id,type,title,body)
                           VALUES (%s,'admin',%s,%s)""",
                        (tg_id, request.form.get("title","").strip(),
                         request.form.get("body","").strip()))
            conn.commit()
        flash("اعلان ارسال شد", "success")
    except Exception as e:
        flash(f"خطا در ارسال اعلان: {e}", "error")
    finally:
        conn.close()
    return redirect(url_for("miniapp_content"))

@app.route("/logout")
def logout():
    session.clear()
    flash("با موفقیت خارج شدید", "success")
    return redirect(url_for("login"))


if __name__ == "__main__":
    print("🌐 پنل مدیریت فرنود در حال اجرا روی http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
from db_extras import list_premium_emojis, add_premium_emoji, delete_premium_emoji, gen_premium_code

