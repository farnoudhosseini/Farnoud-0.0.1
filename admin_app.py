# فایل اصلی پنل مدیریت وب فرنود
# این پنل روی مرورگر باز می‌شود و کاملاً جدا از ربات تلگرام است

from flask import Flask, render_template, request, redirect, url_for, session, flash
from config import SECRET_KEY
from database import check_admin

app = Flask(__name__)
app.secret_key = SECRET_KEY

@app.route("/")
def index():
    """
    صفحه اصلی - اگر لاگین باشد به داشبورد می‌رود
    در غیر این صورت به صفحه لاگین هدایت می‌شود
    """
    if "admin_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    """
    صفحه ورود به پنل مدیریت
    """
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
def dashboard():
    """
    داشبورد اصلی پنل (فعلاً فقط UI)
    """
    if "admin_id" not in session:
        return redirect(url_for("login"))

    return render_template("dashboard.html", username=session.get("admin_username"))

@app.route("/logout")
def logout():
    """
    خروج از پنل
    """
    session.clear()
    flash("با موفقیت خارج شدید", "success")
    return redirect(url_for("login"))

if __name__ == "__main__":
    print("🌐 پنل مدیریت فرنود در حال اجرا روی http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
