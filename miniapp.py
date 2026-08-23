# Telegram Mini App API for FarnoudBot
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
import base64
from datetime import datetime, timezone
from decimal import Decimal
from functools import wraps
from urllib.parse import parse_qsl

from flask import Blueprint, jsonify, request, send_from_directory

from config import BOT_TOKEN
from database import get_sync_connection
from db_users import upsert_bot_user, get_bot_user, count_referrals
from db_products import list_products, get_product
from db_support import list_user_orders, get_user_order
from services.provision import provision_order




DEFAULT_MINIAPP_THEME = {
    "brand_name": "فرنود",
    "brand_sub": "مدیریت سرویس VPN",
    "brand_mark": "F",
    "logo_url": "",
    "welcome_title": "سلام {name}",
    "welcome_subtitle": "سرویس‌ها، کیف پول و باشگاه مشتریان در یکجا",
    "primary": "#9b6cff",
    "primary_2": "#c6a6ff",
    "bg": "#090910",
    "surface": "#141421",
    "text": "#f8f7ff",
    "muted": "#9796a8",
    "success": "#4ed69a",
    "danger": "#ff6e86",
    "warning": "#ffc75b",
    "radius": "18",
    "font": "Vazirmatn",
    "tab_home": "خانه",
    "tab_services": "سرویس‌ها",
    "tab_wallet": "کیف پول",
    "tab_rewards": "باشگاه",
    "tab_profile": "پروفایل",
    "show_rewards": "1",
    "show_news": "1",
    "show_banners": "1",
    "support_url": "",
    "custom_css": "",
}


def get_miniapp_theme() -> dict:
    try:
        from database import get_setting_sync
        raw = get_setting_sync("miniapp_theme", "") or ""
        if raw:
            data = json.loads(raw)
            if isinstance(data, dict):
                out = dict(DEFAULT_MINIAPP_THEME)
                out.update({k: v for k, v in data.items() if v is not None and v != ""})
                return out
    except Exception as e:
        print("theme load:", e)
    return dict(DEFAULT_MINIAPP_THEME)


def save_miniapp_theme(data: dict) -> None:
    from database import set_setting_sync
    base = dict(DEFAULT_MINIAPP_THEME)
    base.update(data or {})
    set_setting_sync("miniapp_theme", json.dumps(base, ensure_ascii=False))


def resolve_miniapp_url() -> str:
    """آدرس عمومی مینی‌اپ از تنظیمات یا محیط"""
    try:
        from database import get_setting_sync
        u = (get_setting_sync("miniapp_url", "") or "").strip()
        if u:
            return u.rstrip("/")
    except Exception:
        pass
    env = (os.getenv("MINIAPP_URL") or "").strip()
    if env:
        return env.rstrip("/")
    return ""


miniapp_bp = Blueprint("miniapp", __name__, url_prefix="/miniapp")
RATE_BUCKET = {}


def _jsonable(v):
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, bytes):
        return None
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return v


def ensure_miniapp_tables():
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            statements = [
                """CREATE TABLE IF NOT EXISTS telegram_accounts (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    telegram_id BIGINT NOT NULL UNIQUE,
                    language_code VARCHAR(16) NULL,
                    photo_url TEXT NULL,
                    auth_date BIGINT NULL,
                    last_auth_at TIMESTAMP NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
                """CREATE TABLE IF NOT EXISTS wallet_transactions (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    telegram_id BIGINT NOT NULL,
                    type VARCHAR(32) NOT NULL,
                    amount DECIMAL(18,0) NOT NULL,
                    balance_after DECIMAL(18,0) NULL,
                    reference_type VARCHAR(32) NULL,
                    reference_id VARCHAR(100) NULL,
                    description VARCHAR(255) NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_wallet_user (telegram_id, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
                """CREATE TABLE IF NOT EXISTS loyalty_accounts (
                    telegram_id BIGINT PRIMARY KEY,
                    points BIGINT NOT NULL DEFAULT 0,
                    level VARCHAR(20) NOT NULL DEFAULT 'Bronze',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
                """CREATE TABLE IF NOT EXISTS loyalty_transactions (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    telegram_id BIGINT NOT NULL,
                    points INT NOT NULL,
                    type VARCHAR(40) NOT NULL,
                    reference_id VARCHAR(100) NULL,
                    description VARCHAR(255) NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_loyalty_user (telegram_id, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
                """CREATE TABLE IF NOT EXISTS referrals (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    referrer_id BIGINT NOT NULL,
                    referred_id BIGINT NOT NULL UNIQUE,
                    code VARCHAR(64) NULL,
                    reward_points INT NOT NULL DEFAULT 0,
                    status VARCHAR(24) NOT NULL DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
                """CREATE TABLE IF NOT EXISTS notifications (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    telegram_id BIGINT NULL,
                    type VARCHAR(40) NOT NULL,
                    title VARCHAR(160) NOT NULL,
                    body TEXT NOT NULL,
                    action_url VARCHAR(500) NULL,
                    is_read TINYINT(1) NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_notification_user (telegram_id, is_read, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
                """CREATE TABLE IF NOT EXISTS news (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    summary TEXT NULL,
                    content LONGTEXT NULL,
                    image_url VARCHAR(1000) NULL,
                    published_at TIMESTAMP NULL,
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_news (is_active, published_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
                """CREATE TABLE IF NOT EXISTS banners (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    image_url VARCHAR(1000) NULL,
                    title VARCHAR(200) NOT NULL,
                    description TEXT NULL,
                    cta VARCHAR(80) NULL,
                    link VARCHAR(1000) NULL,
                    start_date TIMESTAMP NULL,
                    end_date TIMESTAMP NULL,
                    priority INT NOT NULL DEFAULT 0,
                    target_role VARCHAR(30) NOT NULL DEFAULT 'all',
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_banner (is_active, priority)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
                """CREATE TABLE IF NOT EXISTS coupons (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    code VARCHAR(64) NOT NULL UNIQUE,
                    discount_type VARCHAR(16) NOT NULL DEFAULT 'percent',
                    discount_value DECIMAL(18,2) NOT NULL DEFAULT 0,
                    min_order_amount DECIMAL(18,0) NOT NULL DEFAULT 0,
                    max_uses INT NULL,
                    used_count INT NOT NULL DEFAULT 0,
                    expires_at TIMESTAMP NULL,
                    is_active TINYINT(1) NOT NULL DEFAULT 1
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
                """CREATE TABLE IF NOT EXISTS coupon_uses (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    coupon_id BIGINT NOT NULL,
                    telegram_id BIGINT NOT NULL,
                    order_id BIGINT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uniq_coupon_user (coupon_id, telegram_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
                """CREATE TABLE IF NOT EXISTS system_settings (
                    `key` VARCHAR(100) PRIMARY KEY,
                    `value` TEXT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            ]
            for sql in statements:
                cur.execute(sql)
            # Safe additive migration for service_orders; existing bot flows remain untouched.
            for col, ddl in [
                ("miniapp_order_key", "VARCHAR(80) NULL UNIQUE"),
                ("coupon_code", "VARCHAR(64) NULL"),
                ("discount_amount", "DECIMAL(18,0) NOT NULL DEFAULT 0"),
                ("provision_error", "TEXT NULL"),
            ]:
                try:
                    cur.execute(f"ALTER TABLE service_orders ADD COLUMN {col} {ddl}")
                except Exception:
                    pass
            cur.execute("INSERT IGNORE INTO settings (`key`,`value`) VALUES ('miniapp_enabled','1')")
            try:
                cur.execute("INSERT IGNORE INTO settings (`key`,`value`) VALUES ('miniapp_url','')")
            except Exception:
                pass
            conn.commit()
    finally:
        conn.close()


try:
    ensure_miniapp_tables()
except Exception as exc:
    print("Mini App migration warning:", exc)


def _validate_init_data(init_data: str):
    """اعتبارسنجی initData طبق الگوریتم رسمی تلگرام / پیاده‌سازی PHP."""
    token = (BOT_TOKEN or "").strip().strip('"').strip("'")
    if not token:
        return None, "BOT_TOKEN روی سرور تنظیم نشده"
    if not init_data:
        return None, "داده احراز هویت تلگرام موجود نیست — از داخل ربات باز کنید"
    try:
        # parse_qsl یک‌بار URL-decode می‌کند (مطابق مشخصات)
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        supplied_hash = pairs.pop("hash", None)
        # فیلد signature برای third-party است؛ برای بات نادیده بگیر
        pairs.pop("signature", None)
        if not supplied_hash:
            return None, "داده احراز هویت تلگرام ناقص است"
        data_check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs.keys()))
        # PHP: hash_hmac('sha256', $bot_token, 'WebAppData', true)
        # یعنی key=WebAppData ، message=bot_token
        secret = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
        expected = hmac.new(secret, data_check.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, supplied_hash):
            # fallback: بعضی مستندات قدیمی ترتیب را برعکس نوشته‌اند
            secret2 = hmac.new(token.encode("utf-8"), b"WebAppData", hashlib.sha256).digest()
            expected2 = hmac.new(secret2, data_check.encode("utf-8"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected2, supplied_hash):
                return None, "امضای تلگرام نامعتبر است"
        auth_date = int(pairs.get("auth_date") or 0)
        max_age = int(os.getenv("TELEGRAM_INIT_DATA_MAX_AGE", "86400"))
        if auth_date > 0 and time.time() - auth_date > max_age:
            return None, "نشست تلگرام منقضی شده — اپ را ببندید و دوباره باز کنید"
        user_raw = pairs.get("user")
        if not user_raw:
            return None, "اطلاعات کاربر تلگرام موجود نیست"
        user = json.loads(user_raw)
        if not user.get("id"):
            return None, "شناسه کاربر نامعتبر است"
        return user, None
    except Exception as e:
        print("initData validate error:", e)
        return None, "خطا در احراز هویت تلگرام"


def _rate_limit(user_id: int, action: str, limit=30, window=60):
    now = time.time()
    key = (user_id, action)
    bucket = RATE_BUCKET.get(key, [])
    bucket = [x for x in bucket if now - x < window]
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    RATE_BUCKET[key] = bucket
    return True


def auth_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        init_data = request.headers.get("X-Telegram-Init-Data", "")
        user, error = _validate_init_data(init_data)
        if error:
            return jsonify({"ok": False, "error": error}), 401
        if not _rate_limit(int(user["id"]), request.endpoint or "api"):
            return jsonify({"ok": False, "error": "کمی بعد دوباره تلاش کنید."}), 429
        request.tg_user = user
        try:
            db_user = upsert_bot_user(_TelegramUser(user))
            request.db_user = db_user
            _sync_telegram_account(user)
        except Exception as exc:
            return jsonify({"ok": False, "error": f"خطای ثبت کاربر: {exc}"}), 500
        return fn(*args, **kwargs)
    return wrapped


class _TelegramUser:
    def __init__(self, data):
        self.id = int(data["id"])
        self.username = data.get("username")
        self.first_name = data.get("first_name")
        self.last_name = data.get("last_name")


def _sync_telegram_account(user):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO telegram_accounts
                   (telegram_id, language_code, photo_url, auth_date, last_auth_at)
                   VALUES (%s,%s,%s,%s,NOW())
                   ON DUPLICATE KEY UPDATE language_code=VALUES(language_code),
                   photo_url=VALUES(photo_url), auth_date=VALUES(auth_date), last_auth_at=NOW()""",
                (user["id"], user.get("language_code"), user.get("photo_url"),
                 int(user.get("auth_date", 0)) if user.get("auth_date") else None),
            )
            conn.commit()
    finally:
        conn.close()


def _level(points):
    points = int(points or 0)
    if points >= 15000:
        return "Diamond", 15000, None
    if points >= 7500:
        return "Gold", 7500, 15000
    if points >= 2500:
        return "Silver", 2500, 7500
    return "Bronze", 0, 2500


def _loyalty(user_id):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM loyalty_accounts WHERE telegram_id=%s", (user_id,))
            row = cur.fetchone()
            if not row:
                cur.execute("INSERT INTO loyalty_accounts (telegram_id) VALUES (%s)", (user_id,))
                conn.commit()
                points = 0
            else:
                points = row["points"]
            level, current_min, next_min = _level(points)
            if not row or row["level"] != level:
                cur.execute("UPDATE loyalty_accounts SET level=%s WHERE telegram_id=%s", (level, user_id))
                conn.commit()
            return {"points": points, "level": level, "current_min": current_min,
                    "next_min": next_min, "progress": 1 if not next_min else min(1, max(0, (points-current_min)/(next_min-current_min)))}
    finally:
        conn.close()


def _wallet_transactions(user_id, limit=20):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id,type,amount,balance_after,description,created_at
                           FROM wallet_transactions WHERE telegram_id=%s
                           ORDER BY id DESC LIMIT %s""", (user_id, limit))
            return [_jsonable(x) for x in (cur.fetchall() or [])]
    finally:
        conn.close()


def _subscriptions(user_id):
    rows = list_user_orders(user_id)
    out = []
    for o in rows:
        p = get_product(o["product_id"]) if o.get("product_id") else None
        out.append(_subscription_payload(o, p))
    return out


def _subscription_payload(o, product=None):
    volume = float((o.get("volume_gb_override") if o.get("volume_gb_override") is not None else (product or {}).get("volume_gb") or 0))
    duration = int((o.get("duration_days_override") if o.get("duration_days_override") is not None else (product or {}).get("duration_days") or 0))
    status = o.get("status") or "—"
    if status == "provisioned":
        status = "active"
    expire = o.get("expire_at")
    remaining_days = duration
    if expire:
        try:
            dt = expire if isinstance(expire, datetime) else datetime.fromisoformat(str(expire).replace("Z","+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            remaining_days = max(0, int((dt - datetime.now(timezone.utc)).total_seconds()/86400))
        except Exception:
            pass
    return {
        "id": o.get("id"), "name": o.get("custom_name") or (product or {}).get("name") or "سرویس",
        "product_name": (product or {}).get("name"), "status": status,
        "volume_gb": volume, "remaining_gb": volume, "duration_days": duration,
        "remaining_days": remaining_days, "expire_at": _jsonable(expire),
        "vpn_username": o.get("vpn_username"), "panel_id": o.get("panel_id"),
        "amount": _jsonable(o.get("amount") or 0),
        "subscription_link": None,
    }


def _plans(user_id):
    u = get_bot_user(user_id) or {}
    products = list_products(role=u.get("role") or "all", active_only=True)
    result = []
    for p in products:
        panels = p.get("panels") or []
        result.append({
            "id": p["id"], "name": p["name"], "description": p.get("description") or "",
            "price": _jsonable(p["price"]), "volume_gb": _jsonable(p["volume_gb"]),
            "duration_days": p.get("duration_days"), "hwid_limit": p.get("hwid_limit"),
            "category": p.get("category_name") or "VPN", "popular": p.get("sort_order",0) == 0,
            "panels": [_jsonable(x) for x in panels],
        })
    return result


def _content(user_id, role):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT * FROM news WHERE is_active=1
                           AND (published_at IS NULL OR published_at<=NOW())
                           ORDER BY COALESCE(published_at,created_at) DESC LIMIT 8""")
            news = cur.fetchall() or []
            cur.execute("""SELECT * FROM banners WHERE is_active=1
                           AND (start_date IS NULL OR start_date<=NOW())
                           AND (end_date IS NULL OR end_date>=NOW())
                           AND (target_role='all' OR target_role=%s)
                           ORDER BY priority DESC,id DESC LIMIT 5""", (role or "user",))
            banners = cur.fetchall() or []
            return _jsonable({"news": news, "banners": banners})
    finally:
        conn.close()


def _notifications(user_id, limit=30):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT id,type,title,body,action_url,is_read,created_at
                           FROM notifications
                           WHERE telegram_id IS NULL OR telegram_id=%s
                           ORDER BY id DESC LIMIT %s""", (user_id, limit))
            rows = cur.fetchall() or []
            cur.execute("""SELECT COUNT(*) AS c FROM notifications
                           WHERE is_read=0 AND (telegram_id IS NULL OR telegram_id=%s)""", (user_id,))
            unread = (cur.fetchone() or {}).get("c",0)
            return _jsonable({"items": rows, "unread": unread})
    finally:
        conn.close()


def _referrals(user_id):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT invite_code FROM bot_users WHERE telegram_id=%s", (user_id,))
            me = cur.fetchone() or {}
            cur.execute("SELECT COUNT(*) c FROM bot_users WHERE referrer_id=%s", (user_id,))
            total = (cur.fetchone() or {}).get("c",0)
            cur.execute("""SELECT COUNT(*) c FROM bot_users b
                           WHERE b.referrer_id=%s AND b.last_seen_at IS NOT NULL""", (user_id,))
            active = (cur.fetchone() or {}).get("c",0)
            return {"code": me.get("invite_code"), "total": total, "active": active,
                    "link": f"https://t.me/{os.getenv('BOT_USERNAME','')}?start=ref_{me.get('invite_code','')}" if os.getenv("BOT_USERNAME") else None}
    finally:
        conn.close()


def _dashboard(user_id):
    subs = _subscriptions(user_id)
    active = [s for s in subs if s["status"] in ("active","provisioned")]
    primary = active[0] if active else (subs[0] if subs else None)
    user = get_bot_user(user_id) or {}
    return {"subscription": primary, "subscriptions": subs, "has_subscription": bool(subs),
            "status": primary["status"] if primary else "no_subscription",
            "balance": _jsonable(user.get("balance") or 0),
            "loyalty": _loyalty(user_id),
            "referrals": _referrals(user_id)}


@miniapp_bp.get("/")
def miniapp_index():
    root = os.path.join(os.path.dirname(__file__), "static", "miniapp")
    return send_from_directory(root, "index.html")


@miniapp_bp.get("/assets/<path:filename>")
def miniapp_asset(filename):
    """سرویس CSS/JS/فونت مینی‌اپ از مسیر ثابت /miniapp/assets/..."""
    root = os.path.join(os.path.dirname(__file__), "static", "miniapp")
    return send_from_directory(root, filename)


@miniapp_bp.get("/api/theme")
def miniapp_theme_api():
    return jsonify({"ok": True, "theme": get_miniapp_theme()})


@miniapp_bp.get("/api/bootstrap")
@auth_required
def bootstrap():
    user_id = int(request.tg_user["id"])
    role = (request.db_user or {}).get("role") or "user"
    def safe(fn, default):
        try:
            return fn()
        except Exception as e:
            print("bootstrap part error:", fn, e)
            return default
    content = safe(lambda: _content(user_id, role), {"news": [], "banners": []})
    if not isinstance(content, dict):
        content = {"news": [], "banners": []}
    payload = {
        "ok": True,
        "theme": get_miniapp_theme(),
        "user": _jsonable(request.db_user),
        "dashboard": safe(lambda: _dashboard(user_id), {"subscription": None, "subscriptions": [], "has_subscription": False, "status": "no_subscription", "balance": 0}),
        "plans": safe(lambda: _plans(user_id), []),
        "wallet": {
            "balance": _jsonable((request.db_user or {}).get("balance") or 0),
            "transactions": safe(lambda: _wallet_transactions(user_id), []),
        },
        "loyalty": safe(lambda: _loyalty(user_id), {"points": 0, "level": "Bronze", "current_min": 0, "next_min": 2500, "progress": 0}),
        "referrals": safe(lambda: _referrals(user_id), {"code": None, "total": 0, "active": 0, "link": None}),
        "notifications": safe(lambda: _notifications(user_id), {"items": [], "unread": 0}),
    }
    payload.update(content)
    return jsonify(payload)


@miniapp_bp.get("/api/subscriptions/<int:order_id>")
@auth_required
def subscription_detail(order_id):
    o = get_user_order(order_id, int(request.tg_user["id"]))
    if not o:
        return jsonify({"ok": False, "error": "سرویس پیدا نشد"}), 404
    p = get_product(o["product_id"])
    payload = _subscription_payload(o, p)
    # Live connection information is intentionally fetched only on demand.
    if o.get("vpn_username"):
        try:
            from services.panel_client import get_panel_client
            from database import get_panel_by_id
            from services.provision import fix_subscription_url
            panel = get_panel_by_id(o.get("panel_id")) if o.get("panel_id") else None
            if not panel:
                panel = {
                    "base_url": o.get("base_url") or o.get("panel_base") or "",
                    "username": o.get("panel_user") or "",
                    "password": o.get("panel_pass") or "",
                    "panel_type": o.get("panel_type") or "pasarguard",
                    "api_key": o.get("api_key") or "",
                }
            client = get_panel_client(panel)
            full = client.get_user(o["vpn_username"]) or {}
            raw = full.get("subscription_url") or full.get("subscription_link") or ""
            if not raw and full.get("subscription_token"):
                raw = f"/sub/{full['subscription_token']}"
            if not raw and full.get("subId") and hasattr(client, "subscription_url"):
                try:
                    raw = client.subscription_url(full.get("subId"), email=o["vpn_username"])
                except Exception:
                    pass
            base = (panel.get("base_url") if isinstance(panel, dict) else "") or ""
            payload["subscription_link"] = raw if str(raw).startswith("http") else fix_subscription_url(base, raw)
            if payload["subscription_link"]:
                try:
                    qr_bytes = __import__("services.provision", fromlist=["make_qr_png"]).make_qr_png(payload["subscription_link"])
                    if qr_bytes:
                        payload["qr_data_url"] = "data:image/png;base64," + base64.b64encode(qr_bytes).decode()
                except Exception:
                    pass
            used = int(full.get("used_traffic") or 0)
            limit = int(full.get("data_limit") or 0)
            payload["used_bytes"] = used
            payload["total_bytes"] = limit
            payload["remaining_bytes"] = max(0, limit-used) if limit else None
            if full.get("expire"):
                payload["expire_at"] = full.get("expire")
        except Exception as exc:
            payload["live_error"] = str(exc)
    return jsonify({"ok": True, "subscription": _jsonable(payload)})


def _calculate_discount(user_id, product, code):
    if not code:
        return 0, None
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT * FROM coupons WHERE code=%s AND is_active=1
                           AND (expires_at IS NULL OR expires_at>=NOW())
                           AND (max_uses IS NULL OR used_count<max_uses)""", (code.strip(),))
            c = cur.fetchone()
            if not c:
                return 0, "کد تخفیف معتبر نیست."
            cur.execute("SELECT 1 FROM coupon_uses WHERE coupon_id=%s AND telegram_id=%s", (c["id"], user_id))
            if cur.fetchone():
                return 0, "این کد را قبلاً استفاده کرده‌اید."
            price = Decimal(str(product["price"]))
            if price < Decimal(str(c["min_order_amount"] or 0)):
                return 0, "حداقل مبلغ سفارش رعایت نشده است."
            if c["discount_type"] == "percent":
                d = price * Decimal(str(c["discount_value"])) / Decimal(100)
            else:
                d = Decimal(str(c["discount_value"]))
            return int(max(0, min(price, d))), None
    finally:
        conn.close()


@miniapp_bp.post("/api/orders")
@auth_required
def create_mini_order():
    user_id = int(request.tg_user["id"])
    body = request.get_json(silent=True) or {}
    try:
        product_id = int(body.get("product_id"))
    except Exception:
        return jsonify({"ok": False, "error": "پلن نامعتبر است"}), 400
    idempotency = (request.headers.get("Idempotency-Key") or body.get("idempotency_key") or "").strip()
    if not idempotency or len(idempotency) > 80:
        return jsonify({"ok": False, "error": "شناسه سفارش نامعتبر است"}), 400
    coupon_code = (body.get("coupon_code") or "").strip()
    product = get_product(product_id)
    if not product or not product.get("is_active"):
        return jsonify({"ok": False, "error": "پلن در دسترس نیست"}), 404
    panel_id = body.get("panel_id")
    panels = product.get("panels") or []
    if panel_id is None:
        if len(panels) != 1:
            return jsonify({"ok": False, "error": "لوکیشن سرویس را انتخاب کنید"}), 400
        panel_id = panels[0]["id"]
    try:
        panel_id = int(panel_id)
    except Exception:
        return jsonify({"ok": False, "error": "لوکیشن نامعتبر است"}), 400
    if panel_id not in [int(x["id"]) for x in panels]:
        return jsonify({"ok": False, "error": "این لوکیشن برای پلن فعال نیست"}), 400

    discount, discount_error = _calculate_discount(user_id, product, coupon_code)
    if discount_error:
        return jsonify({"ok": False, "error": discount_error}), 400
    amount = max(0, int(Decimal(str(product["price"])) - Decimal(discount)))

    conn = get_sync_connection()
    order_id = None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM service_orders WHERE miniapp_order_key=%s", (idempotency,))
            existing = cur.fetchone()
            if existing:
                return _order_response(existing, "این سفارش قبلاً ثبت شده است.")
            cur.execute("SELECT * FROM bot_users WHERE telegram_id=%s FOR UPDATE", (user_id,))
            user = cur.fetchone()
            if not user or int(user.get("balance") or 0) < amount:
                return jsonify({"ok": False, "error": "موجودی کیف پول کافی نیست.", "required": amount,
                                "balance": int(user.get("balance") or 0) if user else 0}), 402
            cur.execute("""UPDATE bot_users SET balance=balance-%s WHERE telegram_id=%s AND balance>=%s""",
                        (amount, user_id, amount))
            if cur.rowcount != 1:
                conn.rollback()
                return jsonify({"ok": False, "error": "موجودی تغییر کرده است؛ دوباره تلاش کنید."}), 409
            cur.execute("""INSERT INTO service_orders
                           (telegram_id,product_id,panel_id,amount,wallet_used,pay_amount,status,
                            miniapp_order_key,coupon_code,discount_amount)
                           VALUES (%s,%s,%s,%s,%s,0,'paid',%s,%s,%s)""",
                        (user_id,product_id,panel_id,amount,amount,idempotency,coupon_code or None,discount))
            order_id = cur.lastrowid
            new_balance = int(user["balance"]) - amount
            cur.execute("""INSERT INTO wallet_transactions
                           (telegram_id,type,amount,balance_after,reference_type,reference_id,description)
                           VALUES (%s,'purchase',%s,%s,'order',%s,%s)""",
                        (user_id,-amount,new_balance,str(order_id),f"خرید {product.get('name') or 'سرویس'}"))
            if discount:
                cur.execute("""INSERT INTO coupon_uses (coupon_id,telegram_id,order_id)
                               SELECT id,%s,%s FROM coupons WHERE code=%s""", (user_id,order_id,coupon_code))
                cur.execute("UPDATE coupons SET used_count=used_count+1 WHERE code=%s", (coupon_code,))
            conn.commit()
    except Exception:
        conn.rollback()
        return jsonify({"ok": False, "error": "ثبت سفارش انجام نشد. دوباره تلاش کنید."}), 500
    finally:
        conn.close()

    result = provision_order(order_id)
    if not result.get("ok"):
        conn = get_sync_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE service_orders SET status='paid',provision_error=%s WHERE id=%s",
                            (result.get("error") or "Provision failed", order_id))
                cur.execute("UPDATE bot_users SET balance=balance+%s WHERE telegram_id=%s",
                            (amount,user_id))
                cur.execute("""INSERT INTO wallet_transactions
                               (telegram_id,type,amount,balance_after,reference_type,reference_id,description)
                               SELECT telegram_id,'refund',%s,balance,'order',%s,%s
                               FROM bot_users WHERE telegram_id=%s""",
                            (amount, order_id, "بازگشت وجه خرید ناموفق", user_id))
                conn.commit()
        finally:
            conn.close()
        return jsonify({"ok": False, "error": "ساخت سرویس انجام نشد؛ مبلغ به کیف پول برگشت."}), 502

    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO loyalty_accounts (telegram_id,points,level)
                           VALUES (%s,%s,'Bronze')
                           ON DUPLICATE KEY UPDATE points=points+VALUES(points)""",
                        (user_id, max(1, amount // 10000)))
            cur.execute("""INSERT INTO loyalty_transactions
                           (telegram_id,points,type,reference_id,description)
                           VALUES (%s,%s,'purchase',%s,%s)""",
                        (user_id, max(1, amount // 10000), str(order_id), "امتیاز خرید"))
            points = max(1, amount // 10000)
            cur.execute("""INSERT INTO notifications (telegram_id,type,title,body)
                           VALUES (%s,'purchase','خرید موفق',%s)""",
                        (user_id, f"سرویس {product.get('name') or ''} با موفقیت فعال شد."))
            conn.commit()
    finally:
        conn.close()
    order = get_user_order(order_id, user_id) or {}
    return _order_response(order, "خرید با موفقیت انجام شد.", result)


def _order_response(order, message, provision=None):
    return jsonify({"ok": True, "message": message, "order": _jsonable(order),
                    "provision": _jsonable(provision or {})})


@miniapp_bp.post("/api/notifications/read")
@auth_required
def mark_notifications_read():
    body = request.get_json(silent=True) or {}
    nid = body.get("id")
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            if nid:
                cur.execute("""UPDATE notifications SET is_read=1
                               WHERE id=%s AND (telegram_id IS NULL OR telegram_id=%s)""",
                            (int(nid), int(request.tg_user["id"])))
            else:
                cur.execute("""UPDATE notifications SET is_read=1
                               WHERE telegram_id IS NULL OR telegram_id=%s""", (int(request.tg_user["id"]),))
            conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


@miniapp_bp.get("/api/wallet")
@auth_required
def wallet_api():
    user_id = int(request.tg_user["id"])
    user = get_bot_user(user_id) or {}
    return jsonify({"ok": True, "balance": _jsonable(user.get("balance") or 0),
                    "transactions": _wallet_transactions(user_id, 50)})


@miniapp_bp.post("/api/wallet/topup")
@auth_required
def wallet_topup():
    body = request.get_json(silent=True) or {}
    try:
        amount = int(body.get("amount"))
    except Exception:
        return jsonify({"ok": False, "error": "مبلغ نامعتبر است"}), 400
    if amount < int(os.getenv("MIN_CHARGE", "10000")) or amount > int(os.getenv("MAX_CHARGE", "50000000")):
        return jsonify({"ok": False, "error": "مبلغ خارج از محدوده مجاز است"}), 400
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM payment_cards WHERE is_active=1 ORDER BY sort_order,id LIMIT 1")
            card = cur.fetchone()
            if not card:
                return jsonify({"ok": False, "error": "در حال حاضر روش پرداخت فعالی وجود ندارد"}), 503
            cur.execute("""INSERT INTO charge_requests
                           (telegram_id,amount,method_key,card_id,status)
                           VALUES (%s,%s,'card',%s,'waiting_receipt')""",
                        (int(request.tg_user["id"]), amount, card["id"]))
            charge_id = cur.lastrowid
            conn.commit()
            return jsonify({"ok": True, "charge_id": charge_id,
                            "card": _jsonable(card),
                            "message": "واریز را انجام دهید و رسید را از طریق ربات ارسال کنید."})
    finally:
        conn.close()


@miniapp_bp.post("/api/referrals/copy")
@auth_required
def referral_copy():
    # Kept server-side for auditability; actual clipboard operation is client-side.
    return jsonify({"ok": True, "referrals": _referrals(int(request.tg_user["id"]))})


@miniapp_bp.errorhandler(Exception)
def miniapp_error(error):
    print("Mini App error:", error)
    return jsonify({"ok": False, "error": "خطای غیرمنتظره‌ای رخ داد."}), 500
