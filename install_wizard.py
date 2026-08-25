# -*- coding: utf-8 -*-
"""
نصب‌کننده وب FarnoudBot برای cPanel / aaPanel / هاست
پس از نصب موفق، فایل .installed ساخته می‌شود و مسیر /install غیرفعال می‌گردد.
"""

from __future__ import annotations

import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template_string, request, url_for
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
INSTALLED_FLAG = BASE_DIR / ".installed"
SCHEMA_PATH = BASE_DIR / "models_schema.sql"

install_bp = Blueprint("install_wizard", __name__)

INSTALL_HTML = r"""
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>نصب FarnoudBot</title>
<style>
  :root { --bg:#0f172a; --card:#1e293b; --accent:#38bdf8; --ok:#22c55e; --err:#f87171; --text:#e2e8f0; --muted:#94a3b8; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: Tahoma, Vazirmatn, sans-serif; background: linear-gradient(160deg,#0f172a,#1e3a5f); color:var(--text); min-height:100vh; }
  .wrap { max-width:640px; margin:0 auto; padding:24px 16px 48px; }
  h1 { font-size:1.4rem; margin:0 0 8px; }
  .sub { color:var(--muted); margin-bottom:24px; font-size:.9rem; }
  .card { background:var(--card); border-radius:16px; padding:20px; margin-bottom:16px; border:1px solid #334155; }
  label { display:block; font-size:.85rem; color:var(--muted); margin:12px 0 6px; }
  input, select { width:100%; padding:12px 14px; border-radius:10px; border:1px solid #475569; background:#0f172a; color:var(--text); font-size:1rem; }
  input:focus { outline:2px solid var(--accent); border-color:transparent; }
  .row { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
  @media (max-width:560px){ .row { grid-template-columns:1fr; } }
  .btn { display:inline-block; width:100%; margin-top:20px; padding:14px; border:0; border-radius:12px; background:var(--accent); color:#0f172a; font-weight:700; font-size:1rem; cursor:pointer; }
  .btn:hover { filter:brightness(1.08); }
  .alert { padding:12px 14px; border-radius:10px; margin-bottom:16px; font-size:.9rem; }
  .alert.err { background:#450a0a; color:#fecaca; border:1px solid #7f1d1d; }
  .alert.ok { background:#052e16; color:#bbf7d0; border:1px solid #14532d; }
  .steps { display:flex; gap:8px; margin-bottom:20px; flex-wrap:wrap; }
  .steps span { background:#334155; padding:6px 12px; border-radius:999px; font-size:.75rem; color:var(--muted); }
  .steps span.on { background:var(--accent); color:#0f172a; font-weight:700; }
  .hint { font-size:.78rem; color:var(--muted); margin-top:4px; }
  code { background:#0f172a; padding:2px 6px; border-radius:4px; font-size:.85em; }
</style>
</head>
<body>
<div class="wrap">
  <h1>🚀 نصب FarnoudBot</h1>
  <p class="sub">نصب‌کننده وب برای هاست / cPanel / aaPanel — فقط یک‌بار اجرا شود.</p>
  <div class="steps">
    <span class="on">۱. اطلاعات</span>
    <span>۲. دیتابیس</span>
    <span>۳. ربات</span>
    <span>۴. پایان</span>
  </div>
  {% if error %}
  <div class="alert err">{{ error }}</div>
  {% endif %}
  {% if success %}
  <div class="alert ok">{{ success|safe }}</div>
  {% else %}
  <form method="post" action="{{ action }}">
    <div class="card">
      <strong>دیتابیس MySQL</strong>
      <div class="row">
        <div>
          <label>هاست دیتابیس</label>
          <input name="db_host" value="{{ form.db_host }}" required>
        </div>
        <div>
          <label>پورت</label>
          <input name="db_port" value="{{ form.db_port }}" required>
        </div>
      </div>
      <label>نام دیتابیس</label>
      <input name="db_name" value="{{ form.db_name }}" required>
      <div class="row">
        <div>
          <label>کاربر دیتابیس</label>
          <input name="db_user" value="{{ form.db_user }}" required>
        </div>
        <div>
          <label>رمز دیتابیس</label>
          <input name="db_password" type="password" value="{{ form.db_password }}" required>
        </div>
      </div>
      <p class="hint">در cPanel نام دیتابیس معمولاً شبیه <code>user_farnoudbot</code> است.</p>
    </div>
    <div class="card">
      <strong>ربات تلگرام</strong>
      <label>توکن ربات (BotFather)</label>
      <input name="bot_token" value="{{ form.bot_token }}" required placeholder="123456:ABC...">
      <label>آیدی عددی ادمین</label>
      <input name="admin_id" value="{{ form.admin_id }}" required placeholder="از @userinfobot">
      <label>یوزرنیم ربات (بدون @)</label>
      <input name="bot_username" value="{{ form.bot_username }}" placeholder="MyShopBot">
    </div>
    <div class="card">
      <strong>دامنه و حالت اجرا</strong>
      <label>آدرس عمومی HTTPS (بدون اسلش انتها)</label>
      <input name="public_base_url" value="{{ form.public_base_url }}" required placeholder="https://bot.example.com">
      <p class="hint">همین آدرس برای Mini App و Webhook استفاده می‌شود.</p>
      <label>حالت ربات</label>
      <select name="use_webhook">
        <option value="1" {% if form.use_webhook=='1' %}selected{% endif %}>Webhook — مناسب cPanel / هاست اشتراکی</option>
        <option value="0" {% if form.use_webhook=='0' %}selected{% endif %}>Polling — مناسب VPS / aaPanel با Supervisor</option>
      </select>
      <label>رمز ورود پنل وب (کاربر: admin)</label>
      <input name="web_password" type="text" value="{{ form.web_password }}" required minlength="8">
      <p class="hint">این رمز را ذخیره کنید؛ بعداً از پنل قابل تغییر است.</p>
    </div>
    <button class="btn" type="submit">شروع نصب</button>
  </form>
  {% endif %}
</div>
</body>
</html>
"""


def is_installed() -> bool:
    if INSTALLED_FLAG.exists():
        return True
    if not ENV_PATH.exists():
        return False
    try:
        text = ENV_PATH.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    token = ""
    for line in text.splitlines():
        if line.startswith("BOT_TOKEN="):
            token = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
    if not token or token in ("YOUR_TELEGRAM_BOT_TOKEN", "CHANGE_ME", ""):
        return False
    return True


def _safe(s: str) -> str:
    return (s or "").strip()


def _write_env(data: dict) -> None:
    secret = secrets.token_urlsafe(36)
    wh_secret = secrets.token_urlsafe(24)
    content = f"""BOT_TOKEN={data['bot_token']}
ADMIN_ID={data['admin_id']}
SECRET_KEY={secret}

DB_HOST={data['db_host']}
DB_PORT={data['db_port']}
DB_USER={data['db_user']}
DB_PASSWORD={data['db_password']}
DB_NAME={data['db_name']}

BOT_USERNAME={data['bot_username']}
TELEGRAM_INIT_DATA_MAX_AGE=86400
MIN_CHARGE=10000
MAX_CHARGE=50000000
MINIAPP_URL={data['public_base_url'].rstrip('/')}/miniapp/
PUBLIC_BASE_URL={data['public_base_url'].rstrip('/')}

USE_WEBHOOK={data['use_webhook']}
WEBHOOK_PATH=/telegram/webhook
WEBHOOK_SECRET={wh_secret}
"""
    ENV_PATH.write_text(content, encoding="utf-8")
    try:
        os.chmod(ENV_PATH, 0o600)
    except Exception:
        pass


def _test_db(data: dict) -> None:
    import pymysql
    conn = pymysql.connect(
        host=data["db_host"],
        port=int(data["db_port"]),
        user=data["db_user"],
        password=data["db_password"],
        database=data["db_name"],
        charset="utf8mb4",
        connect_timeout=10,
    )
    conn.close()


def _import_schema(data: dict) -> None:
    import pymysql
    conn = pymysql.connect(
        host=data["db_host"],
        port=int(data["db_port"]),
        user=data["db_user"],
        password=data["db_password"],
        database=data["db_name"],
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        # جدا کردن دستورات ساده
        parts = re.split(r";\s*\n", sql)
        with conn.cursor() as cur:
            for part in parts:
                stmt = part.strip()
                if not stmt or stmt.startswith("--"):
                    continue
                try:
                    cur.execute(stmt)
                except Exception as e:
                    # جداول تکراری را نادیده بگیر
                    if "already exists" in str(e).lower():
                        continue
                    # بعضی INSERT IGNORE خطا نمی‌دهند
                    print("schema stmt warn:", e)
        # ادمین پنل
        pw_hash = generate_password_hash(data["web_password"])
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS admins (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(64) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            cur.execute(
                """
                INSERT INTO admins (username, password) VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE password=VALUES(password)
                """,
                ("admin", pw_hash),
            )
    finally:
        conn.close()


def _set_webhook(data: dict) -> str:
    if data.get("use_webhook") != "1":
        return "حالت Polling — وب‌هوک ست نشد (عمدی)."
    try:
        import requests
        from dotenv import load_dotenv
        load_dotenv(ENV_PATH)
        secret = ""
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.startswith("WEBHOOK_SECRET="):
                secret = line.split("=", 1)[1].strip()
        url = data["public_base_url"].rstrip("/") + "/telegram/webhook"
        api = f"https://api.telegram.org/bot{data['bot_token']}/setWebhook"
        r = requests.get(api, params={"url": url, "secret_token": secret, "drop_pending_updates": True}, timeout=20)
        j = r.json()
        if j.get("ok"):
            return f"وب‌هوک ست شد: {url}"
        return f"ست وب‌هوک ناموفق: {j}"
    except Exception as e:
        return f"ست وب‌هوک با خطا: {e}"


@install_bp.route("/install", methods=["GET", "POST"])
@install_bp.route("/install/", methods=["GET", "POST"])
def install_page():
    if is_installed():
        return (
            "<html dir='rtl'><body style='font-family:Tahoma;padding:40px'>"
            "<h2>نصب قبلاً انجام شده است.</h2>"
            "<p>برای نصب مجدد فایل <code>.installed</code> و در صورت نیاز <code>.env</code> را حذف کنید.</p>"
            "<p><a href='/'>ورود به پنل</a></p></body></html>"
        ), 200

    form = {
        "db_host": "localhost",
        "db_port": "3306",
        "db_name": "",
        "db_user": "",
        "db_password": "",
        "bot_token": "",
        "admin_id": "",
        "bot_username": "",
        "public_base_url": (request.host_url or "").rstrip("/").replace("http://", "https://") if request else "",
        "use_webhook": "1",
        "web_password": secrets.token_urlsafe(10),
    }

    if request.method == "POST":
        for k in form:
            if k in request.form:
                form[k] = _safe(request.form.get(k))
        error = None
        if not re.match(r"^\d+:[\w-]+$", form["bot_token"]):
            # توکن‌ها متنوع‌اند؛ فقط خالی نبودن سخت‌گیرانه
            if len(form["bot_token"]) < 20:
                error = "توکن ربات معتبر به نظر نمی‌رسد."
        if not form["admin_id"].isdigit():
            error = "آیدی ادمین باید فقط عدد باشد."
        if not form["public_base_url"].startswith("http"):
            error = "آدرس عمومی باید با https:// شروع شود."
        if len(form["web_password"]) < 8:
            error = "رمز پنل حداقل ۸ کاراکتر باشد."

        if not error:
            try:
                _test_db(form)
                _write_env(form)
                # بارگذاری مجدد env برای ادامه
                from dotenv import load_dotenv
                load_dotenv(ENV_PATH, override=True)
                _import_schema(form)
                wh_msg = _set_webhook(form)
                INSTALLED_FLAG.write_text("installed\n", encoding="utf-8")
                success = (
                    f"<b>نصب با موفقیت انجام شد.</b><br><br>"
                    f"• ورود پنل: کاربر <code>admin</code><br>"
                    f"• رمز پنل: <code>{form['web_password']}</code><br>"
                    f"• Mini App: <code>{form['public_base_url'].rstrip('/')}/miniapp/</code><br>"
                    f"• {wh_msg}<br><br>"
                    f"ابتدا اپلیکیشن Python / gunicorn را <b>Restart</b> کنید تا تنظیمات جدید بارگذاری شود.<br>سپس دکمه منوی مینی‌اپ را در BotFather تنظیم کنید و "
                    f"با <code>/setgroup</code> گروه گزارش را ست کنید.<br><br>"
                    f"<a href='/' style='color:#38bdf8'>ورود به پنل مدیریت</a>"
                )
                return render_template_string(
                    INSTALL_HTML,
                    form=form,
                    error=None,
                    success=success,
                    action=url_for("install_wizard.install_page"),
                )
            except Exception as e:
                error = f"خطا در نصب: {e}"

        return render_template_string(
            INSTALL_HTML,
            form=form,
            error=error,
            success=None,
            action=url_for("install_wizard.install_page"),
        )

    # حدس دامنه از درخواست
    if request and request.host:
        form["public_base_url"] = f"https://{request.host}"

    return render_template_string(
        INSTALL_HTML,
        form=form,
        error=None,
        success=None,
        action=url_for("install_wizard.install_page"),
    )


def register_install_wizard(app):
    """ثبت بلوپرینت نصب‌کننده وب."""
    app.register_blueprint(install_bp)

    @app.before_request
    def _force_install():
        # هر درخواست دوباره چک می‌شود تا بعد از نصب (بدون ری‌استارت فوری) قفل باز شود
        if is_installed():
            return None
        from flask import request as req
        path = (req.path or "").rstrip("/")
        if path in ("/install",) or path.startswith("/static"):
            return None
        return redirect("/install")
