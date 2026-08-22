# پنل مدیریت وب فرنود

from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from config import SECRET_KEY
from database import (
    check_admin,
    get_setting_sync,
    set_setting_sync,
    ensure_tables_sync,
    list_panels,
    get_panel_by_id,
    get_panel_by_slug,
    create_panel,
    update_panel_status,
    delete_panel,
)
from services.pasarguard import PasarGuardClient, normalize_base_url

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
    return render_template(
        "dashboard.html",
        username=session.get("admin_username"),
        active="dashboard",
        panels_count=len(panels),
    )


# ---------- تنظیم پیام‌های ربات ----------

@app.route("/bot-messages", methods=["GET", "POST"])
@login_required
def bot_messages():
    """بخش تنظیم پیام‌های ربات — زیرمجموعه: پیام خوش‌آمد"""
    if request.method == "POST":
        welcome = request.form.get("welcome_message", "").strip()
        if not welcome:
            flash("پیام خوش‌آمدگویی نمی‌تواند خالی باشد", "error")
        else:
            if set_setting_sync("welcome_message", welcome):
                flash("پیام خوش‌آمدگویی ذخیره شد", "success")
            else:
                flash("خطا در ذخیره پیام", "error")
        return redirect(url_for("bot_messages"))

    current_welcome = get_setting_sync("welcome_message", "سلام! به ربات فرنود خوش آمدید 👋")
    return render_template(
        "bot_messages.html",
        username=session.get("admin_username"),
        active="bot_messages",
        welcome_message=current_welcome,
    )


# ---------- مدیریت پنل‌های VPN ----------

@app.route("/panels")
@login_required
def panels_list():
    panels = list_panels()
    return render_template(
        "panels.html",
        username=session.get("admin_username"),
        active="panels",
        panels=panels,
    )


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
            flash("فعلاً فقط پنل پاسارگارد پشتیبانی می‌شود", "error")
            return render_template("panel_add.html", username=session.get("admin_username"), active="panels")

        if not all([name, raw_url, username, password]):
            flash("تمام فیلدها الزامی هستند", "error")
            return render_template("panel_add.html", username=session.get("admin_username"), active="panels")

        try:
            base_url = normalize_base_url(raw_url)
        except ValueError as e:
            flash(str(e), "error")
            return render_template("panel_add.html", username=session.get("admin_username"), active="panels")

        # تست اتصال واقعی
        try:
            client = PasarGuardClient(base_url, username, password, verify_ssl=False)
            client.test_connection()
        except PermissionError as e:
            flash(str(e), "error")
            return render_template("panel_add.html", username=session.get("admin_username"), active="panels")
        except ConnectionError as e:
            flash(str(e), "error")
            return render_template("panel_add.html", username=session.get("admin_username"), active="panels")
        except Exception as e:
            flash(f"اتصال ناموفق: {e}", "error")
            return render_template("panel_add.html", username=session.get("admin_username"), active="panels")

        panel_id, slug = create_panel(name, panel_type, base_url, username, password)
        if not panel_id:
            flash("خطا در ذخیره پنل در دیتابیس", "error")
            return render_template("panel_add.html", username=session.get("admin_username"), active="panels")

        flash(f"پنل «{name}» با موفقیت متصل شد", "success")
        return redirect(url_for("panel_detail", slug=slug))

    return render_template(
        "panel_add.html",
        username=session.get("admin_username"),
        active="panels",
    )


@app.route("/panels/<slug>")
@login_required
def panel_detail(slug):
    panel = get_panel_by_slug(slug)
    if not panel:
        flash("پنل یافت نشد", "error")
        return redirect(url_for("panels_list"))

    stats = None
    error = None
    if panel["panel_type"] == "pasarguard":
        try:
            client = PasarGuardClient(
                panel["base_url"],
                panel["username"],
                panel["password"],
                verify_ssl=False,
            )
            stats = client.get_system_stats()
            update_panel_status(panel["id"], "online")
        except Exception as e:
            error = str(e)
            update_panel_status(panel["id"], "offline")

    return render_template(
        "panel_detail.html",
        username=session.get("admin_username"),
        active="panels",
        panel=panel,
        stats=stats,
        error=error,
    )


@app.route("/panels/<int:panel_id>/delete", methods=["POST"])
@login_required
def panels_delete(panel_id):
    if delete_panel(panel_id):
        flash("پنل حذف شد", "success")
    else:
        flash("حذف پنل ناموفق بود", "error")
    return redirect(url_for("panels_list"))


@app.route("/personalize")
@login_required
def personalize():
    return render_template(
        "personalize.html",
        username=session.get("admin_username"),
        active="personalize",
    )


@app.route("/logout")
def logout():
    session.clear()
    flash("با موفقیت خارج شدید", "success")
    return redirect(url_for("login"))


if __name__ == "__main__":
    print("🌐 پنل مدیریت فرنود در حال اجرا روی http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
