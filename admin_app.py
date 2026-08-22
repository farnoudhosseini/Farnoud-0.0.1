# فایل اصلی پنل مدیریت وب فرنود
# این پنل روی مرورگر باز می‌شود و کاملاً جدا از ربات تلگرام است

from flask import Flask, render_template, request, redirect, url_for, session, flash
from config import SECRET_KEY
from database import check_admin, get_setting_sync, set_setting_sync, ensure_tables_sync

app = Flask(__name__)
app.secret_key = SECRET_KEY

# اطمینان از وجود جداول هنگام شروع
try:
    ensure_tables_sync()
except Exception:
    pass

def login_required(f):
    """دکوراتور بررسی لاگین"""
    from functools import wraps
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
        else:
            flash("نام کاربری یا رمز عبور اشتباه است", "error")

    return render_template("login.html")

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", username=session.get("admin_username"), active="dashboard")

@app.route("/bot-settings", methods=["GET", "POST"])
@login_required
def bot_settings():
    """تنظیمات ربات - پیام خوش‌آمدگویی"""
    if request.method == "POST":
        welcome = request.form.get("welcome_message", "").strip()
        if not welcome:
            flash("پیام خوش‌آمدگویی نمی‌تواند خالی باشد", "error")
        else:
            if set_setting_sync("welcome_message", welcome):
                flash("پیام خوش‌آمدگویی ذخیره شد", "success")
            else:
                flash("خطا در ذخیره پیام", "error")
        return redirect(url_for("bot_settings"))

    current_welcome = get_setting_sync("welcome_message", "سلام! به ربات فرنود خوش آمدید 👋")
    return render_template(
        "bot_settings.html",
        username=session.get("admin_username"),
        active="bot_settings",
        welcome_message=current_welcome,
    )

@app.route("/personalize")
@login_required
def personalize():
    """صفحه شخصی‌سازی ظاهر پنل"""
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
