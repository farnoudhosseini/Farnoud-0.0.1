# -*- coding: utf-8 -*-
"""
FarnoudBot diagnostic installer.

Adds:
- Telegram Bot API live test with getMe
- Webhook status test with getWebhookInfo
- Webhook endpoint test from the server
- MySQL connection test
- Detailed installer log at install.log
- Log viewer/download endpoint
"""

from __future__ import annotations

import html
import json
import os
import re
import secrets
import traceback
from datetime import datetime
from pathlib import Path

from flask import Blueprint, Response, redirect, render_template_string, request, url_for
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
INSTALLED_FLAG = BASE_DIR / ".installed"
SCHEMA_PATH = BASE_DIR / "models_schema.sql"
LOG_PATH = BASE_DIR / "install.log"

install_bp = Blueprint("install_wizard", __name__)


def log(message: str, level: str = "INFO") -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {message}\n"
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def mask_token(token: str) -> str:
    token = token or ""
    if len(token) <= 10:
        return "***"
    return token[:6] + "..." + token[-4:]


def telegram_api(token: str, method: str, params: dict | None = None, timeout: int = 15) -> dict:
    import requests

    if not token:
        raise ValueError("BOT_TOKEN خالی است")

    url = f"https://api.telegram.org/bot{token}/{method}"
    log(f"Telegram API request: {method}")
    r = requests.get(url, params=params or {}, timeout=timeout)
    log(f"Telegram API HTTP {r.status_code} for {method}")
    try:
        data = r.json()
    except Exception:
        log(f"Telegram returned non-JSON: {r.text[:500]}", "ERROR")
        raise RuntimeError(f"Telegram پاسخ JSON معتبر نداد: HTTP {r.status_code}")

    if not data.get("ok"):
        log(f"Telegram API error: {json.dumps(data, ensure_ascii=False)[:1000]}", "ERROR")
        raise RuntimeError(data.get("description") or str(data))

    return data


def test_telegram_token(token: str) -> dict:
    token = (token or "").strip()
    log(f"Testing BOT_TOKEN {mask_token(token)}")
    data = telegram_api(token, "getMe")
    result = data.get("result") or {}
    log(
        "Telegram token OK: "
        f"id={result.get('id')} username=@{result.get('username')} "
        f"name={result.get('first_name')}"
    )
    return result


def test_webhook_info(token: str) -> dict:
    data = telegram_api(token, "getWebhookInfo")
    result = data.get("result") or {}
    log(
        "Webhook info: "
        f"url={result.get('url')!r}, pending={result.get('pending_update_count')}, "
        f"last_error={result.get('last_error_message')!r}"
    )
    return result


def test_public_webhook(url: str, secret: str = "") -> tuple[bool, str]:
    import requests

    url = url.rstrip("/") + "/telegram/webhook"
    log(f"Testing public webhook endpoint: {url}")

    try:
        headers = {}
        if secret:
            headers["X-Telegram-Bot-Api-Secret-Token"] = secret
        # GET is expected to return 405 because endpoint accepts POST.
        r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        log(f"Webhook endpoint HTTP {r.status_code}: {r.text[:300]!r}")
        if r.status_code in (405, 400):
            return True, f"Endpoint reachable (HTTP {r.status_code})"
        if r.status_code == 403:
            return False, "Endpoint reachable but secret-token check rejected the test"
        if 200 <= r.status_code < 300:
            return True, f"Endpoint reachable (HTTP {r.status_code})"
        return False, f"Endpoint returned HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        log(f"Webhook endpoint connection failed: {e}", "ERROR")
        return False, str(e)


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
    return bool(token and token not in ("YOUR_TELEGRAM_BOT_TOKEN", "CHANGE_ME"))


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
    log(".env written successfully")


def _test_db(data: dict) -> None:
    import pymysql

    log(
        f"Testing MySQL: host={data['db_host']} port={data['db_port']} "
        f"db={data['db_name']} user={data['db_user']}"
    )
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
    log("MySQL connection OK")


def _import_schema(data: dict) -> None:
    import pymysql

    log("Importing database schema")
    conn = pymysql.connect(
        host=data["db_host"],
        port=int(data["db_port"]),
        user=data["db_user"],
        password=data["db_password"],
        database=data["db_name"],
        charset="utf8mb4",
        autocommit=True,
        connect_timeout=10,
    )
    try:
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        parts = re.split(r";\s*\n", sql)
        with conn.cursor() as cur:
            for part in parts:
                stmt = part.strip()
                if not stmt or stmt.startswith("--"):
                    continue
                try:
                    cur.execute(stmt)
                except Exception as e:
                    if "already exists" in str(e).lower():
                        continue
                    log(f"Schema statement warning: {e}", "WARN")

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
        log("Database schema/admin setup OK")
    finally:
        conn.close()


def _set_webhook(data: dict) -> str:
    if data.get("use_webhook") != "1":
        log("Polling selected; webhook setup skipped")
        return "حالت Polling انتخاب شده؛ وب‌هوک تنظیم نشد."

    try:
        from dotenv import load_dotenv

        load_dotenv(ENV_PATH, override=True)

        secret = ""
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.startswith("WEBHOOK_SECRET="):
                secret = line.split("=", 1)[1].strip()

        url = data["public_base_url"].rstrip("/") + "/telegram/webhook"
        log(f"Setting Telegram webhook: {url}")

        result = telegram_api(
            data["bot_token"],
            "setWebhook",
            {
                "url": url,
                "secret_token": secret,
                "drop_pending_updates": True,
            },
            timeout=20,
        )
        log(f"setWebhook result: {json.dumps(result, ensure_ascii=False)[:1000]}")

        info = test_webhook_info(data["bot_token"])
        actual = info.get("url") or ""
        if actual.rstrip("/") != url.rstrip("/"):
            raise RuntimeError(
                f"وب‌هوک تنظیم شد ولی getWebhookInfo آدرس دیگری برگرداند: {actual}"
            )

        ok, msg = test_public_webhook(data["public_base_url"], secret)
        if not ok:
            log(f"Webhook public endpoint warning: {msg}", "WARN")

        return f"وب‌هوک تنظیم و تأیید شد: {url}<br>تست Endpoint: {html.escape(msg)}"
    except Exception as e:
        log(f"Webhook setup failed: {e}", "ERROR")
        raise


INSTALL_HTML = r"""
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>نصب و عیب‌یابی FarnoudBot</title>
<style>
:root{--bg:#0b1220;--card:#172033;--line:#2d3b52;--accent:#38bdf8;--ok:#22c55e;--err:#ef4444;--warn:#f59e0b;--text:#e5edf7;--muted:#9fb0c5}
*{box-sizing:border-box}body{margin:0;font-family:Tahoma,Vazirmatn,sans-serif;background:linear-gradient(160deg,#0b1220,#17304d);color:var(--text);min-height:100vh}
.wrap{max-width:760px;margin:auto;padding:22px 14px 50px}h1{font-size:1.35rem;margin:0 0 8px}.sub{color:var(--muted);font-size:.88rem;margin:0 0 18px}
.card{background:rgba(23,32,51,.96);border:1px solid var(--line);border-radius:16px;padding:18px;margin-bottom:14px}
label{display:block;color:var(--muted);font-size:.82rem;margin:11px 0 6px}input,select{width:100%;padding:12px;border-radius:10px;border:1px solid #40506a;background:#0b1220;color:var(--text);font-size:.95rem}
input:focus,select:focus{outline:2px solid var(--accent);border-color:transparent}.row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:600px){.row{grid-template-columns:1fr}}button{border:0;border-radius:10px;padding:12px 15px;font-weight:700;cursor:pointer}.btn{width:100%;margin-top:15px;background:var(--accent);color:#06121c}.btn2{background:#26354b;color:var(--text);margin-top:10px;width:100%}
.alert{padding:12px;border-radius:10px;margin-bottom:14px;font-size:.88rem;line-height:1.8}.ok{background:#052e16;border:1px solid #166534;color:#bbf7d0}.err{background:#450a0a;border:1px solid #991b1b;color:#fecaca}.warn{background:#451a03;border:1px solid #92400e;color:#fde68a}
pre{white-space:pre-wrap;word-break:break-word;background:#070c15;border:1px solid #26354b;border-radius:10px;padding:12px;max-height:330px;overflow:auto;direction:ltr;text-align:left;font:12px/1.6 monospace}
.badge{display:inline-block;padding:5px 9px;border-radius:999px;background:#26354b;color:var(--muted);font-size:.72rem}.hint{color:var(--muted);font-size:.76rem;line-height:1.7}
</style>
</head>
<body>
<div class="wrap">
<h1>🛠️ نصب و عیب‌یابی FarnoudBot</h1>
<p class="sub">قبل از نصب، اتصال Bot API و دیتابیس را واقعاً تست می‌کند و تمام مراحل را در install.log ثبت می‌کند.</p>

{% if error %}<div class="alert err">❌ {{ error }}</div>{% endif %}
{% if success %}<div class="alert ok">✅ {{ success|safe }}</div>{% endif %}
{% if test_result %}<div class="alert {{ 'ok' if test_result.ok else 'err' }}">{{ test_result.message|safe }}</div>{% endif %}

<form method="post" action="{{ action }}">
<div class="card">
<strong>🤖 تست Bot API</strong>
<label>توکن ربات Telegram</label>
<input name="bot_token" value="{{ form.bot_token }}" required placeholder="123456789:AA...">
<p class="hint">این دکمه مستقیماً متد getMe تلگرام را صدا می‌زند. اگر توکن اشتباه باشد، همان‌جا خطای واقعی API نمایش داده می‌شود.</p>
<button class="btn2" type="submit" name="action" value="test_api">🔎 تست API و نمایش اطلاعات ربات</button>
</div>

<div class="card">
<strong>🗄️ MySQL</strong>
<div class="row">
<div><label>هاست دیتابیس</label><input name="db_host" value="{{ form.db_host }}" required></div>
<div><label>پورت</label><input name="db_port" value="{{ form.db_port }}" required></div>
</div>
<label>نام دیتابیس</label><input name="db_name" value="{{ form.db_name }}" required>
<div class="row">
<div><label>کاربر دیتابیس</label><input name="db_user" value="{{ form.db_user }}" required></div>
<div><label>رمز دیتابیس</label><input name="db_password" type="password" value="{{ form.db_password }}" required></div>
</div>
</div>

<div class="card">
<strong>🌐 تنظیمات ربات</strong>
<label>آیدی عددی ادمین</label>
<input name="admin_id" value="{{ form.admin_id }}" required placeholder="123456789">
<label>یوزرنیم ربات بدون @</label>
<input name="bot_username" value="{{ form.bot_username }}" placeholder="MyBot">
<label>آدرس عمومی HTTPS</label>
<input name="public_base_url" value="{{ form.public_base_url }}" required placeholder="https://example.com">
<label>حالت اجرا</label>
<select name="use_webhook">
<option value="1" {% if form.use_webhook=='1' %}selected{% endif %}>Webhook (cPanel / هاست)</option>
<option value="0" {% if form.use_webhook=='0' %}selected{% endif %}>Polling (VPS / Supervisor)</option>
</select>
<label>رمز ورود پنل وب</label>
<input name="web_password" type="text" value="{{ form.web_password }}" required minlength="8">
</div>

<div class="card">
<strong>📋 لاگ نصب</strong>
<p class="hint">لاگ در فایل <code>install.log</code> کنار همین فایل ذخیره می‌شود. توکن کامل در لاگ نوشته نمی‌شود.</p>
<a href="{{ log_url }}" style="color:#38bdf8">نمایش لاگ فعلی</a>
</div>

<button class="btn" type="submit" name="action" value="install">🚀 تست کامل و نصب</button>
</form>
</div>
</body>
</html>
"""


def _default_form():
    return {
        "db_host": "localhost",
        "db_port": "3306",
        "db_name": "",
        "db_user": "",
        "db_password": "",
        "bot_token": "",
        "admin_id": "",
        "bot_username": "",
        "public_base_url": (request.host_url or "").rstrip("/").replace("http://", "https://"),
        "use_webhook": "1",
        "web_password": secrets.token_urlsafe(10),
    }


@install_bp.route("/install/log", methods=["GET"])
def install_log():
    try:
        text = LOG_PATH.read_text(encoding="utf-8", errors="replace") if LOG_PATH.exists() else "No log yet."
    except Exception as e:
        text = f"Cannot read log: {e}"
    return Response(text, mimetype="text/plain; charset=utf-8")


@install_bp.route("/install", methods=["GET", "POST"])
@install_bp.route("/install/", methods=["GET", "POST"])
def install_page():
    if is_installed():
        return (
            "<html dir='rtl'><body style='font-family:Tahoma;padding:40px'>"
            "<h2>نصب قبلاً انجام شده است.</h2>"
            "<p>برای نصب مجدد فایل <code>.installed</code> و در صورت نیاز <code>.env</code> را حذف کنید.</p>"
            "<p><a href='/'>ورود به پنل</a></p>"
            "<p><a href='/install/log'>مشاهده لاگ نصب</a></p>"
            "</body></html>"
        ), 200

    form = _default_form()
    error = None
    success = None
    test_result = None

    if request.method == "POST":
        for k in form:
            if k in request.form:
                form[k] = _safe(request.form.get(k))

        action = request.form.get("action", "install")
        log(f"Installer POST action={action}")

        if action == "test_api":
            try:
                me = test_telegram_token(form["bot_token"])
                info = test_webhook_info(form["bot_token"])
                wh = info.get("url") or "(بدون وب‌هوک)"
                last_error = info.get("last_error_message") or "ندارد"
                test_result = {
                    "ok": True,
                    "message": (
                        f"Bot API سالم است ✅<br>"
                        f"ربات: <b>@{html.escape(me.get('username') or 'بدون یوزرنیم')}</b><br>"
                        f"ID: <code>{me.get('id')}</code><br>"
                        f"Webhook فعلی: <code>{html.escape(wh)}</code><br>"
                        f"آخرین خطای Telegram: <code>{html.escape(last_error)}</code>"
                    ),
                }
            except Exception as e:
                log(f"Manual API test failed: {e}", "ERROR")
                test_result = {"ok": False, "message": f"تست API ناموفق بود ❌<br><code>{html.escape(str(e))}</code>"}

        elif action == "install":
            if not re.match(r"^\d+:[\w-]+$", form["bot_token"]):
                if len(form["bot_token"]) < 20:
                    error = "توکن ربات معتبر به نظر نمی‌رسد."
            if not form["admin_id"].isdigit():
                error = "آیدی ادمین باید فقط عدد باشد."
            if not form["public_base_url"].startswith("https://"):
                error = "آدرس عمومی باید با https:// شروع شود."
            if len(form["web_password"]) < 8:
                error = "رمز پنل حداقل ۸ کاراکتر باشد."

            if not error:
                try:
                    log("=" * 70)
                    log("START FULL INSTALL")

                    me = test_telegram_token(form["bot_token"])
                    log(f"Bot verified: @{me.get('username')}")

                    _test_db(form)
                    _write_env(form)

                    from dotenv import load_dotenv
                    load_dotenv(ENV_PATH, override=True)
                    log("Environment loaded")

                    _import_schema(form)

                    wh_msg = _set_webhook(form)

                    INSTALLED_FLAG.write_text("installed\n", encoding="utf-8")
                    log("INSTALLED_FLAG created")
                    log("INSTALL SUCCESS")

                    success = (
                        "<b>نصب با موفقیت انجام شد.</b><br><br>"
                        f"ربات: <code>@{html.escape(me.get('username') or '')}</code><br>"
                        "کاربر پنل: <code>admin</code><br>"
                        f"رمز پنل: <code>{html.escape(form['web_password'])}</code><br>"
                        f"Mini App: <code>{html.escape(form['public_base_url'].rstrip('/') + '/miniapp/')}</code><br>"
                        f"{wh_msg}<br><br>"
                        "حالا Python App / Passenger را Restart کنید و سپس در تلگرام /start را بزنید."
                    )
                    return render_template_string(
                        INSTALL_HTML,
                        form=form,
                        error=None,
                        success=success,
                        test_result=None,
                        action=url_for("install_wizard.install_page"),
                        log_url=url_for("install_wizard.install_log"),
                    )
                except Exception as e:
                    log(f"INSTALL FAILED: {type(e).__name__}: {e}", "ERROR")
                    log(traceback.format_exc(), "ERROR")
                    error = f"نصب متوقف شد: {e}"

    return render_template_string(
        INSTALL_HTML,
        form=form,
        error=error,
        success=success,
        test_result=test_result,
        action=url_for("install_wizard.install_page"),
        log_url=url_for("install_wizard.install_log"),
    )


def register_install_wizard(app):
    app.register_blueprint(install_bp)
    log("Install wizard registered")

    @app.before_request
    def _force_install():
        if is_installed():
            return None
        from flask import request as req
        path = (req.path or "").rstrip("/")
        if path in ("/install", "/install/log") or path.startswith("/static"):
            return None
        return redirect("/install")
