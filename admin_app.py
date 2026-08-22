# پنل مدیریت وب فرنود

from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from config import SECRET_KEY
from database import (
    check_admin, get_setting_sync, set_setting_sync, ensure_tables_sync,
    list_panels, get_panel_by_id, get_panel_by_slug, create_panel,
    update_panel_status, delete_panel,
)
from services.pasarguard import PasarGuardClient, normalize_base_url, bytes_to_gb

app = Flask(__name__)
app.secret_key = SECRET_KEY

try:
    ensure_tables_sync()
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
    panels = list_panels()
    return render_template("dashboard.html", username=session.get("admin_username"), active="dashboard", panels_count=len(panels))


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
                for_create=True,
            )
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
                for_create=False,
            )
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
