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
from urllib.parse import parse_qsl, quote as url_quote

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
    "show_trial": "1",
    "support_url": "",
    "home_cta_buy": "خرید سرویس جدید",
    "home_cta_manage": "مدیریت سرویس",
    "empty_services_title": "سرویسی ندارید",
    "empty_services_body": "اولین سرویس خود را فعال کنید",
    "buy_step1_title": "سرویس شما کجا ارائه می‌شود؟",
    "buy_step2_title": "دسته‌بندی مناسب را انتخاب کنید",
    "buy_step3_title": "محصول مورد نظر را انتخاب کنید",
    "buy_step4_title": "تأیید و پرداخت",
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
                    UNIQUE KEY uniq_loyalty_ref (telegram_id, type, reference_id),
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
        # Telegram initData is application/x-www-form-urlencoded. Keep the
        # decoded values for the official data-check-string construction.
        raw_pairs = parse_qsl(init_data, keep_blank_values=True)
        pairs = dict(raw_pairs)
        supplied_hash = pairs.get("hash")
        if not supplied_hash:
            return None, "داده احراز هویت تلگرام ناقص است"

        # Official Web App validation:
        # secret_key = HMAC-SHA256(key="WebAppData", msg=BOT_TOKEN)
        # hash       = HMAC-SHA256(key=secret_key, msg=data_check_string)
        #
        # Newer Telegram initData may also carry `signature`. Accept both
        # canonical hash variants so the bot-token validation works across
        # Telegram client versions, while every candidate still has to match
        # an HMAC generated from the configured BOT_TOKEN.
        candidates = []
        for include_signature in (False, True):
            check_pairs = {
                k: v for k, v in pairs.items()
                if k != "hash" and (include_signature or k != "signature")
            }
            data_check = "\n".join(
                f"{k}={check_pairs[k]}" for k in sorted(check_pairs.keys())
            )
            secret = hmac.new(
                b"WebAppData", token.encode("utf-8"), hashlib.sha256
            ).digest()
            expected = hmac.new(
                secret, data_check.encode("utf-8"), hashlib.sha256
            ).hexdigest()
            candidates.append(expected)

        if not any(hmac.compare_digest(expected, supplied_hash) for expected in candidates):
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
        if db_user and db_user.get("is_blocked"):
            return jsonify({"ok": False, "error": "دسترسی شما مسدود است."}), 403
        return fn(*args, **kwargs)
    return wrapped


class _TelegramUser:
    def __init__(self, data):
        self.id = int(data["id"])
        self.username = data.get("username")
        self.first_name = data.get("first_name")
        self.last_name = data.get("last_name")


def _auth_gate(user_id: int, tg_user: dict):
    """Enforce force-join channel and force-phone before miniapp use."""
    from database import get_setting_sync
    issues = []
    # channel
    if get_setting_sync("force_join_enabled", "0") == "1":
        ch = (get_setting_sync("force_join_channel", "") or "").strip()
        if ch:
            token = (BOT_TOKEN or "").strip().strip('"').strip("'")
            member = False
            try:
                import urllib.request
                chat = ch if ch.startswith("@") or ch.startswith("-") else ("@" + ch.lstrip("@"))
                if ch.lstrip("-").isdigit():
                    chat = ch
                url = f"https://api.telegram.org/bot{token}/getChatMember?chat_id={url_quote(str(chat))}&user_id={user_id}"
                with urllib.request.urlopen(url, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    st = ((data.get("result") or {}).get("status") or "")
                    member = st in ("creator", "administrator", "member", "restricted")
            except Exception as e:
                print("channel check miniapp:", e)
                member = True  # fail-open to avoid locking everyone on API errors
            if not member:
                issues.append({
                    "type": "channel",
                    "channel": ch,
                    "message": get_setting_sync("force_join_msg", "") or f"ابتدا در کانال عضو شوید: {ch}",
                })
    # phone
    if get_setting_sync("force_phone_enabled", "0") == "1":
        bu = get_bot_user(user_id) or {}
        if not bu.get("phone"):
            issues.append({
                "type": "phone",
                "message": get_setting_sync("force_phone_msg", "") or "برای ادامه، شماره موبایل را از داخل ربات ارسال کنید.",
            })
    return issues



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


def get_loyalty_config():
    """Configurable levels + reward packages for club."""
    default = {
        "levels": [
            {"name": "Bronze", "min_points": 0},
            {"name": "Silver", "min_points": 2500},
            {"name": "Gold", "min_points": 7500},
            {"name": "Diamond", "min_points": 15000},
        ],
        "packages": [],  # [{id, title, points_cost, description, reward_type, reward_value, min_level}]
    }
    try:
        from database import get_setting_sync
        import json as _json
        raw = get_setting_sync("loyalty_config", "") or ""
        if raw:
            data = _json.loads(raw)
            if isinstance(data, dict):
                out = dict(default)
                if isinstance(data.get("levels"), list) and data["levels"]:
                    out["levels"] = data["levels"]
                if isinstance(data.get("packages"), list):
                    out["packages"] = data["packages"]
                return out
    except Exception as e:
        print("loyalty_config:", e)
    return default


def save_loyalty_config(data: dict):
    from database import set_setting_sync
    set_setting_sync("loyalty_config", json.dumps(data or {}, ensure_ascii=False))


def _level(points):
    points = int(points or 0)
    levels = sorted(get_loyalty_config().get("levels") or [], key=lambda x: int(x.get("min_points") or 0))
    if not levels:
        return "Bronze", 0, 2500
    current = levels[0]
    nxt = None
    for i, lv in enumerate(levels):
        if points >= int(lv.get("min_points") or 0):
            current = lv
            nxt = levels[i + 1] if i + 1 < len(levels) else None
        else:
            break
    cur_min = int(current.get("min_points") or 0)
    next_min = int(nxt.get("min_points")) if nxt else None
    return current.get("name") or "Bronze", cur_min, next_min


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
            pts_to_next = None if next_min is None else max(0, int(next_min) - int(points))
            prog = 1 if not next_min else min(1, max(0, (points - current_min) / max(1, (next_min - current_min))))
            return {
                "points": points,
                "level": level,
                "current_min": current_min,
                "next_min": next_min,
                "points_to_next": pts_to_next,
                "progress": prog,
            }
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
        "used_bytes": None, "total_bytes": None, "remaining_bytes": None,
    }


def _enrich_subscription_live(payload, o):
    """Fetch live traffic / expire from panel and update remaining_gb, remaining_days, etc."""
    if not o or not o.get("vpn_username"):
        return payload
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
        if payload.get("subscription_link"):
            try:
                qr_bytes = __import__("services.provision", fromlist=["make_qr_png"]).make_qr_png(payload["subscription_link"])
                if qr_bytes:
                    payload["qr_data_url"] = "data:image/png;base64," + base64.b64encode(qr_bytes).decode()
            except Exception:
                pass
        used = int(full.get("used_traffic") or full.get("used") or 0)
        limit = int(full.get("data_limit") or full.get("total") or 0)
        payload["used_bytes"] = used
        payload["total_bytes"] = limit
        payload["remaining_bytes"] = max(0, limit - used) if limit else None
        GB = 1073741824.0
        if limit > 0:
            payload["volume_gb"] = round(limit / GB, 2)
            payload["remaining_gb"] = round(max(0, limit - used) / GB, 2)
        elif used >= 0 and payload.get("volume_gb"):
            # fallback: subtract used from configured volume
            used_gb = used / GB
            payload["remaining_gb"] = max(0.0, round(float(payload["volume_gb"]) - used_gb, 2))
        if full.get("expire"):
            payload["expire_at"] = full.get("expire")
            try:
                exp = full.get("expire")
                dt = exp if isinstance(exp, datetime) else datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                payload["remaining_days"] = max(0, int((dt - datetime.now(timezone.utc)).total_seconds() / 86400))
            except Exception:
                pass
        # status from panel if available
        st = (full.get("status") or full.get("enable") or "").lower() if isinstance(full.get("status") or full.get("enable"), (str, int, bool)) else ""
        if st in ("active", "1", "true", "enabled", True, 1):
            payload["status"] = "active"
        elif st in ("disabled", "0", "false", "disabled", False, 0, "expired"):
            if "expir" in str(st) or payload.get("remaining_days", 1) <= 0:
                payload["status"] = "expired"
            else:
                payload["status"] = "suspended"
    except Exception as exc:
        payload["live_error"] = str(exc)
    return payload


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


def _resolve_bot_username():
    """Resolve bot username from env/config/settings or Telegram getMe."""
    try:
        from config import BOT_USERNAME as CFG_U
        u = (CFG_U or "").strip().lstrip("@")
        if u:
            return u
    except Exception:
        pass
    u = (os.getenv("BOT_USERNAME") or "").strip().lstrip("@")
    if u:
        return u
    try:
        from database import get_setting_sync
        u = (get_setting_sync("bot_username", "") or "").strip().lstrip("@")
        if u:
            return u
    except Exception:
        pass
    # live lookup via getMe (cached in settings)
    try:
        token = (BOT_TOKEN or "").strip().strip('"').strip("'")
        if token:
            import urllib.request
            with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getMe", timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                u = ((data.get("result") or {}).get("username") or "").strip()
                if u:
                    try:
                        from database import set_setting_sync
                        set_setting_sync("bot_username", u)
                    except Exception:
                        pass
                    return u
    except Exception as e:
        print("getMe username:", e)
    return ""


def _referrals(user_id):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT invite_code FROM bot_users WHERE telegram_id=%s", (user_id,))
            me = cur.fetchone() or {}
            cur.execute("SELECT COUNT(*) c FROM bot_users WHERE referrer_id=%s", (user_id,))
            total = (cur.fetchone() or {}).get("c", 0)
            cur.execute("""SELECT COUNT(*) c FROM bot_users b
                           WHERE b.referrer_id=%s AND b.last_seen_at IS NOT NULL""", (user_id,))
            active = (cur.fetchone() or {}).get("c", 0)
            uname = _resolve_bot_username()
            code = me.get("invite_code") or ""
            link = f"https://t.me/{uname}?start=ref_{code}" if uname and code else None
            return {"code": code or None, "total": total, "active": active, "link": link, "bot_username": uname or None}
    finally:
        conn.close()


def _dashboard(user_id):
    subs = _subscriptions(user_id)
    # آخرین سرویس خریداری‌شده (لیست DESC بر اساس id)
    primary = subs[0] if subs else None
    # Live usage for primary so the home ring is accurate (and stays accurate on 10s poll)
    if primary:
        try:
            o = get_user_order(primary["id"], user_id)
            if o:
                _enrich_subscription_live(primary, o)
                # keep list in sync for the same id
                for s in subs:
                    if s.get("id") == primary.get("id"):
                        s.update({
                            "remaining_gb": primary.get("remaining_gb"),
                            "volume_gb": primary.get("volume_gb"),
                            "remaining_days": primary.get("remaining_days"),
                            "status": primary.get("status"),
                            "used_bytes": primary.get("used_bytes"),
                            "total_bytes": primary.get("total_bytes"),
                            "remaining_bytes": primary.get("remaining_bytes"),
                        })
                        break
        except Exception as e:
            print("dashboard live enrich:", e)
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
    from flask import make_response
    root = os.path.join(os.path.dirname(__file__), "static", "miniapp")
    resp = make_response(send_from_directory(root, filename))
    # کش بلندمدت برای فونت/تصویر؛ CSS/JS با ?v= در کلاینت باطل می‌شود
    lower = (filename or "").lower()
    if lower.endswith((".woff2", ".woff", ".ttf", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")):
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


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
    user_payload = _jsonable(request.db_user) or {}
    # merge live Telegram profile photo from initData
    try:
        tg = request.tg_user or {}
        if tg.get("photo_url"):
            user_payload["photo_url"] = tg.get("photo_url")
        if tg.get("first_name") and not user_payload.get("first_name"):
            user_payload["first_name"] = tg.get("first_name")
        if tg.get("last_name") and not user_payload.get("last_name"):
            user_payload["last_name"] = tg.get("last_name")
        if tg.get("username") and not user_payload.get("username"):
            user_payload["username"] = tg.get("username")
    except Exception:
        pass
    auth_issues = safe(lambda: _auth_gate(user_id, request.tg_user or {}), [])
    loy = safe(lambda: _loyalty(user_id), {"points": 0, "level": "Bronze", "current_min": 0, "next_min": 2500, "progress": 0})
    try:
        cfg = get_loyalty_config()
        loy["levels"] = cfg.get("levels") or []
        loy["packages"] = cfg.get("packages") or []
    except Exception:
        loy["levels"] = []
        loy["packages"] = []
    payload = {
        "ok": True,
        "theme": get_miniapp_theme(),
        "user": user_payload,
        "auth_required": bool(auth_issues),
        "auth_issues": auth_issues,
        "dashboard": safe(lambda: _dashboard(user_id), {"subscription": None, "subscriptions": [], "has_subscription": False, "status": "no_subscription", "balance": 0}),
        "plans": safe(lambda: _plans(user_id), []),
        "wallet": {
            "balance": _jsonable((request.db_user or {}).get("balance") or 0),
            "transactions": safe(lambda: _wallet_transactions(user_id), []),
        },
        "loyalty": loy,
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
    # Live traffic + link from panel
    _enrich_subscription_live(payload, o)
    return jsonify({"ok": True, "subscription": _jsonable(payload)})


def _calculate_discount(user_id, product, code):
    """Validate discount without consuming uses. Uses bot discount_codes table."""
    if not code:
        return 0, None
    code = code.strip().upper()
    price = int(Decimal(str(product.get("price") or 0)))
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            # Primary: bot growth discount_codes
            try:
                cur.execute(
                    "SELECT * FROM discount_codes WHERE UPPER(code)=%s AND is_active=1",
                    (code,),
                )
                d = cur.fetchone()
            except Exception:
                d = None
            if d:
                max_uses = int(d.get("max_uses") or 0)
                used = int(d.get("used_count") or 0)
                if max_uses and used >= max_uses:
                    return 0, "ظرفیت کد تکمیل شده است."
                if d.get("percent"):
                    disc = int(price * float(d["percent"]) / 100)
                elif d.get("amount"):
                    disc = int(d["amount"])
                else:
                    disc = 0
                return int(max(0, min(price, disc))), None

            # Fallback: miniapp coupons table
            try:
                cur.execute(
                    """SELECT * FROM coupons WHERE UPPER(code)=%s AND is_active=1
                       AND (expires_at IS NULL OR expires_at>=NOW())
                       AND (max_uses IS NULL OR used_count<max_uses)""",
                    (code,),
                )
                c = cur.fetchone()
            except Exception:
                c = None
            if not c:
                return 0, "کد تخفیف معتبر نیست."
            try:
                cur.execute(
                    "SELECT 1 FROM coupon_uses WHERE coupon_id=%s AND telegram_id=%s",
                    (c["id"], user_id),
                )
                if cur.fetchone():
                    return 0, "این کد را قبلاً استفاده کرده‌اید."
            except Exception:
                pass
            if price < int(c.get("min_order_amount") or 0):
                return 0, "حداقل مبلغ سفارش رعایت نشده است."
            if (c.get("discount_type") or "percent") == "percent":
                disc = int(price * float(c.get("discount_value") or 0) / 100)
            else:
                disc = int(c.get("discount_value") or 0)
            return int(max(0, min(price, disc))), None
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

    from db_growth import award_purchase_points
    points = award_purchase_points(user_id, amount, order_id)
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
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
                            "message": "واریز را انجام دهید و رسید را همین‌جا یا در ربات ارسال کنید."})
    finally:
        conn.close()


@miniapp_bp.post("/api/referrals/copy")
@auth_required
def referral_copy():
    # Kept server-side for auditability; actual clipboard operation is client-side.
    return jsonify({"ok": True, "referrals": _referrals(int(request.tg_user["id"]))})


# ---------------------------------------------------------------------------
# Catalog (step-by-step buy: panel → category → product)
# ---------------------------------------------------------------------------

@miniapp_bp.get("/api/catalog/panels")
@auth_required
def catalog_panels():
    from database import list_panels
    panels = list_panels() or []
    from database import format_entity_label
    out = []
    for p in panels:
        if not p.get("is_active", 1):
            continue
        out.append({
            "id": p["id"],
            "name": format_entity_label(p, for_miniapp=True) or f"پنل {p['id']}",
            "raw_name": p.get("name") or f"پنل {p['id']}",
            "emoji": (p.get("emoji") or ""),
            "description": p.get("description") or "",
        })
    return jsonify({"ok": True, "panels": out})


@miniapp_bp.get("/api/catalog/categories")
@auth_required
def catalog_categories():
    from db_products import list_categories, list_products as lp
    panel_id = request.args.get("panel_id")
    try:
        panel_id = int(panel_id) if panel_id is not None else None
    except Exception:
        return jsonify({"ok": False, "error": "پنل نامعتبر"}), 400
    user_id = int(request.tg_user["id"])
    bu = get_bot_user(user_id) or {}
    role = bu.get("role") or "user"
    products = lp(panel_id=panel_id, role=role, active_only=True) if panel_id else lp(role=role, active_only=True)
    cat_ids = {p.get("category_id") for p in products if p.get("category_id")}
    from database import format_entity_label
    cats_raw = [c for c in (list_categories(active_only=True) or []) if c["id"] in cat_ids]
    cats = []
    for c in cats_raw:
        item = dict(c)
        item["name"] = format_entity_label(c, for_miniapp=True) or c.get("name")
        item["raw_name"] = c.get("name")
        cats.append(item)
    return jsonify({"ok": True, "categories": _jsonable(cats), "has_uncategorized": any(not p.get("category_id") for p in products)})


@miniapp_bp.get("/api/catalog/products")
@auth_required
def catalog_products():
    from db_products import list_products as lp
    from database import get_setting_sync
    panel_id = request.args.get("panel_id")
    category_id = request.args.get("category_id")
    try:
        panel_id = int(panel_id) if panel_id not in (None, "", "null") else None
        category_id = int(category_id) if category_id not in (None, "", "null", "0") else None
    except Exception:
        return jsonify({"ok": False, "error": "پارامتر نامعتبر"}), 400
    user_id = int(request.tg_user["id"])
    bu = get_bot_user(user_id) or {}
    role = bu.get("role") or "user"
    products = lp(panel_id=panel_id, category_id=category_id, role=role, active_only=True) or []
    hourly_global = get_setting_sync("hourly_global_enabled", "0") == "1"
    out = []
    for p in products:
        hourly_ok = bool(hourly_global and p.get("hourly_enabled") and p.get("hourly_price"))
        out.append({
            "id": p["id"],
            "name": p["name"],
            "description": p.get("description") or "",
            "price": _jsonable(p.get("price") or 0),
            "volume_gb": _jsonable(p.get("volume_gb") or 0),
            "duration_days": p.get("duration_days") or 0,
            "hwid_limit": p.get("hwid_limit"),
            "hourly_enabled": hourly_ok,
            "hourly_price": _jsonable(p.get("hourly_price") or 0) if hourly_ok else None,
            "hwid_limit": p.get("hwid_limit"),
            "category_id": p.get("category_id"),
        })
    return jsonify({"ok": True, "products": out})


@miniapp_bp.get("/api/catalog/product/<int:pid>")
@auth_required
def catalog_product_detail(pid):
    from database import get_setting_sync
    product = get_product(pid)
    if not product or not product.get("is_active"):
        return jsonify({"ok": False, "error": "محصول یافت نشد"}), 404
    hourly_global = get_setting_sync("hourly_global_enabled", "0") == "1"
    hourly_ok = bool(hourly_global and product.get("hourly_enabled") and product.get("hourly_price"))
    panels = product.get("panels") or []
    balance = int((get_bot_user(int(request.tg_user["id"])) or {}).get("balance") or 0)
    return jsonify({
        "ok": True,
        "product": {
            "id": product["id"],
            "name": product["name"],
            "description": product.get("description") or "",
            "price": _jsonable(product.get("price") or 0),
            "volume_gb": _jsonable(product.get("volume_gb") or 0),
            "duration_days": product.get("duration_days") or 0,
            "hwid_limit": product.get("hwid_limit"),
            "hourly_enabled": hourly_ok,
            "hourly_price": _jsonable(product.get("hourly_price") or 0) if hourly_ok else None,
            "panels": _jsonable(panels),
        },
        "balance": balance,
    })


# ---------------------------------------------------------------------------
# Orders: prepare → confirm wallet / card / hourly + receipt
# ---------------------------------------------------------------------------

def _tg_api(method, payload=None, files=None):
    """Call Telegram Bot API synchronously."""
    token = (BOT_TOKEN or "").strip().strip('"').strip("'")
    if not token:
        return None
    import urllib.request
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        if files:
            import requests as _req
            r = _req.post(url, data=payload or {}, files=files, timeout=60)
            return r.json() if r.ok else None
        data = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print("tg_api error:", method, e)
        return None


def _notify_user(telegram_id, text, reply_markup=None):
    payload = {"chat_id": telegram_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return _tg_api("sendMessage", payload)


def _notify_admin_order(order_id, text, photo_bytes=None, photo_b64=None):
    from config import ADMIN_ID
    if not ADMIN_ID:
        return
    kb = {
        "inline_keyboard": [[
            {"text": "✅ تایید و ساخت سرویس", "callback_data": f"adm_ord_ok_{order_id}"},
            {"text": "❌ رد", "callback_data": f"adm_ord_no_{order_id}"},
        ]]
    }
    _tg_api("sendMessage", {"chat_id": ADMIN_ID, "text": text, "reply_markup": kb})
    if photo_bytes or photo_b64:
        try:
            import io
            raw = photo_bytes
            if not raw and photo_b64:
                raw = base64.b64decode(photo_b64.split(",")[-1] if "," in photo_b64 else photo_b64)
            files = {"photo": ("receipt.jpg", io.BytesIO(raw), "image/jpeg")}
            _tg_api("sendPhoto", {"chat_id": str(ADMIN_ID), "caption": f"رسید سفارش #{order_id}"}, files=files)
        except Exception as e:
            print("admin photo notify:", e)


@miniapp_bp.post("/api/orders/prepare")
@auth_required
def prepare_order():
    """Create pending order and return payment options (mirrors bot buy flow)."""
    from db_products import create_order, update_order
    from database import get_panel_by_id, get_setting_sync, get_sync_connection
    from datetime import datetime, timezone as tz

    user_id = int(request.tg_user["id"])
    body = request.get_json(silent=True) or {}
    try:
        product_id = int(body.get("product_id"))
        panel_id = int(body.get("panel_id"))
    except Exception:
        return jsonify({"ok": False, "error": "محصول یا پنل نامعتبر"}), 400

    buy_mode = (body.get("mode") or "full").strip()  # full | hourly
    coupon_code = (body.get("coupon_code") or "").strip()

    product = get_product(product_id)
    panel = get_panel_by_id(panel_id)
    if not product or not product.get("is_active") or not panel:
        return jsonify({"ok": False, "error": "محصول یا پنل در دسترس نیست"}), 404

    panels = product.get("panels") or []
    if panel_id not in [int(x["id"]) for x in panels]:
        return jsonify({"ok": False, "error": "این پنل برای محصول فعال نیست"}), 400

    try:
        max_s = panel.get("max_sales")
        if max_s is not None and int(max_s) > 0:
            conn = get_sync_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS c FROM service_orders WHERE panel_id=%s AND status IN ('paid','provisioned')",
                    (panel_id,),
                )
                cnt = int((cur.fetchone() or {}).get("c") or 0)
            conn.close()
            if cnt >= int(max_s):
                return jsonify({"ok": False, "error": "ظرفیت فروش این پنل تکمیل شده است."}), 400
    except Exception as e:
        print("max_sales", e)

    hourly_global = get_setting_sync("hourly_global_enabled", "0") == "1"
    hourly_ok = bool(hourly_global and product.get("hourly_enabled") and product.get("hourly_price"))

    bu = get_bot_user(user_id) or {}
    balance = int(bu.get("balance") or 0)

    if buy_mode == "hourly":
        if not hourly_ok:
            return jsonify({"ok": False, "error": "خرید ساعتی برای این محصول فعال نیست"}), 400
        hprice = int(float(product.get("hourly_price") or 0))
        if balance < hprice:
            return jsonify({
                "ok": False, "error": "موجودی کافی نیست.",
                "required": hprice, "balance": balance,
            }), 402
        order_id = create_order(user_id, product_id, panel_id, hprice, hprice, 0)
        from db_users import add_balance
        add_balance(user_id, -hprice, f"hourly_start#{order_id}")
        now_s = datetime.now(tz.utc).strftime("%Y-%m-%d %H:%M:%S")
        update_order(
            order_id,
            status="paid",
            wallet_used=hprice,
            pay_amount=0,
            is_hourly=1,
            hourly_rate=hprice,
            hourly_active=1,
            hourly_started_at=now_s,
            hourly_last_charge_at=now_s,
        )
        result = provision_order(order_id)
        if result.get("ok"):
            try:
                from db_growth import award_purchase_points
                award_purchase_points(user_id, hprice, order_id)
            except Exception as e:
                print("hourly purchase points:", e)
            _notify_user(
                user_id,
                f"✅ سرویس ساعتی فعال شد.\nهر ساعت {hprice:,} تومان از کیف پول کسر می‌شود.",
            )
            return jsonify({"ok": True, "mode": "hourly", "order_id": order_id, "message": "سرویس ساعتی فعال شد.", "provision": _jsonable(result)})
        return jsonify({"ok": False, "error": result.get("error") or "ساخت سرویس ناموفق"}), 502

    price = int(product.get("price") or 0)
    discount = 0
    if coupon_code:
        discount, derr = _calculate_discount(user_id, product, coupon_code)
        if derr:
            return jsonify({"ok": False, "error": derr}), 400
    final_price = max(0, price - discount)
    wallet_used = min(balance, final_price)
    pay_amount = max(0, final_price - balance)
    order_id = create_order(user_id, product_id, panel_id, final_price, wallet_used, pay_amount)
    # create_order may mark full-wallet orders as "paid"; keep pending until user confirms in miniapp
    try:
        update_order(order_id, status="pending_payment", wallet_used=wallet_used, pay_amount=pay_amount, amount=final_price)
    except Exception as e:
        print("force pending_payment", e)
    if coupon_code and discount:
        try:
            update_order(order_id, coupon_code=coupon_code, discount_amount=discount)
        except Exception:
            pass

    return jsonify({
        "ok": True,
        "mode": "full",
        "order_id": order_id,
        "product_name": product["name"],
        "panel_name": panel.get("name"),
        "price": price,
        "discount": discount,
        "final_price": final_price,
        "balance": balance,
        "wallet_used": wallet_used,
        "pay_amount": pay_amount,
        "can_pay_wallet": pay_amount <= 0,
        "hourly_available": hourly_ok,
        "hourly_price": _jsonable(product.get("hourly_price") or 0) if hourly_ok else None,
        "message": "فاکتور آماده است.",
    })


@miniapp_bp.post("/api/orders/<int:order_id>/confirm-wallet")
@auth_required
def confirm_wallet_order(order_id):
    from db_products import get_order, update_order
    from db_users import add_balance
    user_id = int(request.tg_user["id"])
    order = get_order(order_id)
    if not order or int(order["telegram_id"]) != user_id:
        return jsonify({"ok": False, "error": "سفارش نامعتبر"}), 404
    st = (order.get("status") or "").strip()
    if st not in ("pending_payment", "waiting_receipt", "pending_review"):
        return jsonify({"ok": False, "error": "این سفارش قابل پرداخت نیست", "status": st}), 400
    price = int(order.get("amount") or 0)
    bu = get_bot_user(user_id) or {}
    balance = int(bu.get("balance") or 0)
    if balance < price:
        return jsonify({"ok": False, "error": f"موجودی کافی نیست. موجودی: {balance:,} / لازم: {price:,}",
                        "required": price, "balance": balance}), 402
    add_balance(user_id, -price, f"order#{order_id}")
    update_order(order_id, status="paid", wallet_used=price, pay_amount=0)
    # consume discount code once
    try:
        code = (order.get("coupon_code") or "").strip().upper()
        if code:
            conn = get_sync_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE discount_codes SET used_count=used_count+1 WHERE UPPER(code)=%s AND is_active=1",
                        (code,),
                    )
                    conn.commit()
            finally:
                conn.close()
    except Exception as e:
        print("discount consume:", e)
    result = provision_order(order_id)
    try:
        from db_growth import pay_referral_commission
        pay_referral_commission(user_id, price)
    except Exception:
        pass
    if result.get("ok"):
        try:
            from db_growth import award_purchase_points
            award_purchase_points(user_id, price, order_id)
        except Exception as e:
            print("purchase points:", e)
        _notify_user(user_id, f"✅ سفارش #{order_id} با موفقیت فعال شد.")
        from config import ADMIN_ID
        if ADMIN_ID:
            _notify_user(ADMIN_ID, f"✅ سفارش #{order_id} تحویل شد (کیف پول مینی‌اپ)\nکاربر: {user_id}")
        return jsonify({"ok": True, "message": "خرید با موفقیت انجام شد.", "order_id": order_id, "provision": _jsonable(result)})
    return jsonify({"ok": False, "error": result.get("error") or "ساخت سرویس ناموفق"}), 502


@miniapp_bp.post("/api/orders/<int:order_id>/pay-card")
@auth_required
def pay_card_order(order_id):
    from db_products import get_order, update_order
    from db_users import list_cards
    user_id = int(request.tg_user["id"])
    order = get_order(order_id)
    if not order or int(order["telegram_id"]) != user_id:
        return jsonify({"ok": False, "error": "سفارش نامعتبر"}), 404
    cards = list_cards(active_only=True) or []
    if not cards:
        return jsonify({"ok": False, "error": "کارتی تعریف نشده. با پشتیبانی تماس بگیرید."}), 503
    card = cards[0]
    update_order(order_id, method_key="card", card_id=card["id"], status="waiting_receipt")
    card_num = str(card["card_number"]).replace(" ", "").replace("-", "")
    pay_amount = int(order.get("pay_amount") or order.get("amount") or 0)
    _notify_user(
        user_id,
        f"💳 مبلغ <b>{pay_amount:,}</b> تومان را واریز کنید:\n\n"
        f"شماره کارت: <code>{card_num}</code>\n"
        f"به نام: {card.get('owner_name') or '—'}\n\n"
        f"سپس تصویر رسید را در مینی‌اپ یا ربات ارسال کنید.\n"
        f"سفارش: #{order_id}",
    )
    return jsonify({
        "ok": True,
        "order_id": order_id,
        "pay_amount": pay_amount,
        "card": {
            "id": card["id"],
            "card_number": card_num,
            "owner_name": card.get("owner_name"),
            "bank_name": card.get("bank_name"),
        },
        "message": "واریز را انجام دهید و رسید را آپلود کنید.",
    })


@miniapp_bp.post("/api/orders/<int:order_id>/receipt")
@auth_required
def upload_order_receipt(order_id):
    """Accept receipt photo (base64) from miniapp, store + forward to admin & bot."""
    from db_products import get_order, update_order
    user_id = int(request.tg_user["id"])
    order = get_order(order_id)
    if not order or int(order["telegram_id"]) != user_id:
        return jsonify({"ok": False, "error": "سفارش نامعتبر"}), 404
    if order.get("status") not in ("waiting_receipt", "pending_payment", "pending_review"):
        return jsonify({"ok": False, "error": "این سفارش منتظر رسید نیست"}), 400

    body = request.get_json(silent=True) or {}
    photo_b64 = body.get("photo") or body.get("image") or ""
    if not photo_b64:
        return jsonify({"ok": False, "error": "تصویر رسید ارسال نشده"}), 400

    update_order(order_id, status="pending_review", receipt_file_id=f"miniapp:{order_id}")

    pay_amount = int(order.get("pay_amount") or order.get("amount") or 0)
    wallet_used = int(order.get("wallet_used") or 0)
    admin_text = (
        f"🧾 رسید سفارش سرویس #{order_id} (از مینی‌اپ)\n"
        f"کاربر: {user_id}\n"
        f"مبلغ قابل پرداخت: {pay_amount:,} تومان\n"
        f"(موجودی کیف پول رزرو: {wallet_used:,})"
    )
    _notify_admin_order(order_id, admin_text, photo_b64=photo_b64)
    if _try_auto_approve_order(order_id, user_id):
        _notify_user(user_id, "سفارش #%s به صورت خودکار تایید و سرویس ساخته شد." % order_id)
        return jsonify({"ok": True, "message": "رسید ثبت و به صورت خودکار تایید شد.", "order_id": order_id, "auto_approved": True})
    _notify_user(user_id, "رسید سفارش #%s ثبت شد. پس از تایید ادمین سرویس برایتان ساخته میشود." % order_id)
    return jsonify({"ok": True, "message": "رسید ثبت شد و برای تایید ارسال شد.", "order_id": order_id})


@miniapp_bp.post("/api/orders/<int:order_id>/discount")
@auth_required
def apply_discount(order_id):
    from db_products import get_order, update_order
    user_id = int(request.tg_user["id"])
    body = request.get_json(silent=True) or {}
    code = (body.get("coupon_code") or "").strip()
    order = get_order(order_id)
    if not order or int(order["telegram_id"]) != user_id:
        return jsonify({"ok": False, "error": "سفارش نامعتبر"}), 404
    product = get_product(order["product_id"])
    if not product:
        return jsonify({"ok": False, "error": "محصول نامعتبر"}), 404
    discount, err = _calculate_discount(user_id, product, code)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    price = int(product.get("price") or 0)
    final_price = max(0, price - discount)
    bu = get_bot_user(user_id) or {}
    balance = int(bu.get("balance") or 0)
    wallet_used = min(balance, final_price)
    pay_amount = max(0, final_price - balance)
    try:
        update_order(order_id, amount=final_price, wallet_used=wallet_used, pay_amount=pay_amount,
                     coupon_code=code, discount_amount=discount)
    except Exception:
        update_order(order_id, amount=final_price, wallet_used=wallet_used, pay_amount=pay_amount)
    return jsonify({
        "ok": True,
        "discount": discount,
        "final_price": final_price,
        "wallet_used": wallet_used,
        "pay_amount": pay_amount,
        "can_pay_wallet": pay_amount <= 0,
        "message": f"تخفیف {discount:,} تومان اعمال شد.",
    })


# ---------------------------------------------------------------------------
# Service actions
# ---------------------------------------------------------------------------

@miniapp_bp.post("/api/subscriptions/<int:order_id>/action")
@auth_required
def subscription_action(order_id):
    from db_products import update_order
    user_id = int(request.tg_user["id"])
    o = get_user_order(order_id, user_id)
    if not o:
        return jsonify({"ok": False, "error": "سرویس پیدا نشد"}), 404
    body = request.get_json(silent=True) or {}
    action = (body.get("action") or "").strip()

    if action == "refresh":
        return subscription_detail(order_id)

    if action == "rename":
        name = (body.get("name") or "").strip()[:80]
        if not name:
            return jsonify({"ok": False, "error": "نام خالی است"}), 400
        update_order(order_id, custom_name=name)
        return jsonify({"ok": True, "message": "نام سرویس تغییر کرد.", "name": name})

    if action == "toggle":
        try:
            from services.service_edit import toggle_user
            result = toggle_user(o)
            return jsonify({"ok": True, "message": result.get("message") or "وضعیت تغییر کرد.", "result": _jsonable(result)})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    if action == "reset":
        try:
            from services.service_edit import reset_subscription
            result = reset_subscription(o)
            return jsonify({"ok": True, "message": result.get("message") or "اشتراک بازنشانی شد.", "result": _jsonable(result)})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    if action == "hourly_toggle":
        try:
            from services.service_edit import toggle_hourly
            result = toggle_hourly(o)
            return jsonify({"ok": True, "message": result.get("message") or "وضعیت ساعتی تغییر کرد.", "result": _jsonable(result)})
        except Exception:
            active = not bool(o.get("hourly_active"))
            update_order(order_id, hourly_active=1 if active else 0)
            return jsonify({"ok": True, "message": "سرویس ساعتی " + ("فعال" if active else "متوقف") + " شد."})

    if action == "link":
        return subscription_detail(order_id)

    return jsonify({"ok": False, "error": "عملیات ناشناخته"}), 400


# ---------------------------------------------------------------------------
# Support tickets
# ---------------------------------------------------------------------------

@miniapp_bp.get("/api/support/departments")
@auth_required
def support_departments():
    from db_support import list_departments
    return jsonify({"ok": True, "departments": _jsonable(list_departments(active_only=True) or [])})


@miniapp_bp.get("/api/support/tickets")
@auth_required
def support_tickets_list():
    from db_support import list_user_tickets
    user_id = int(request.tg_user["id"])
    tickets = list_user_tickets(user_id, 40) or []
    return jsonify({"ok": True, "tickets": _jsonable(tickets)})


@miniapp_bp.post("/api/support/tickets")
@auth_required
def support_ticket_create():
    from db_support import create_ticket, add_ticket_message, list_departments
    from config import ADMIN_ID
    user_id = int(request.tg_user["id"])
    body = request.get_json(silent=True) or {}
    try:
        dep_id = int(body.get("department_id"))
    except Exception:
        return jsonify({"ok": False, "error": "دپارتمان نامعتبر"}), 400
    subject = (body.get("subject") or body.get("message") or "پیام پشتیبانی").strip()[:200]
    message = (body.get("message") or subject).strip()
    if not message:
        return jsonify({"ok": False, "error": "متن پیام خالی است"}), 400
    deps = {d["id"] for d in (list_departments(active_only=True) or [])}
    if dep_id not in deps:
        return jsonify({"ok": False, "error": "دپارتمان یافت نشد"}), 404
    tid = create_ticket(user_id, dep_id, subject)
    add_ticket_message(tid, "user", message)
    if ADMIN_ID:
        _notify_user(ADMIN_ID, f"🎫 تیکت جدید #{tid}\nکاربر: {user_id}\nموضوع: {subject}\n\n{message[:500]}")
    return jsonify({"ok": True, "ticket_id": tid, "message": "تیکت ثبت شد."})


@miniapp_bp.get("/api/support/tickets/<int:tid>")
@auth_required
def support_ticket_detail(tid):
    from db_support import get_ticket, get_ticket_messages
    user_id = int(request.tg_user["id"])
    t = get_ticket(tid)
    if not t or int(t["telegram_id"]) != user_id:
        return jsonify({"ok": False, "error": "تیکت یافت نشد"}), 404
    msgs = get_ticket_messages(tid) or []
    return jsonify({"ok": True, "ticket": _jsonable(t), "messages": _jsonable(msgs)})


@miniapp_bp.post("/api/support/tickets/<int:tid>/messages")
@auth_required
def support_ticket_message(tid):
    from db_support import get_ticket, add_ticket_message
    from config import ADMIN_ID
    user_id = int(request.tg_user["id"])
    t = get_ticket(tid)
    if not t or int(t["telegram_id"]) != user_id:
        return jsonify({"ok": False, "error": "تیکت یافت نشد"}), 404
    if t.get("status") == "closed":
        return jsonify({"ok": False, "error": "تیکت بسته شده است"}), 400
    body = request.get_json(silent=True) or {}
    message = (body.get("message") or "").strip()
    if not message:
        return jsonify({"ok": False, "error": "متن خالی است"}), 400
    add_ticket_message(tid, "user", message)
    if ADMIN_ID:
        _notify_user(ADMIN_ID, f"💬 پیام جدید در تیکت #{tid}\nکاربر: {user_id}\n\n{message[:500]}")
    return jsonify({"ok": True, "message": "پیام ارسال شد."})



@miniapp_bp.post("/api/wallet/topup/receipt")
@auth_required
def wallet_topup_receipt():
    """Upload receipt for a charge request created in miniapp."""
    from db_users import get_charge
    from config import ADMIN_ID
    user_id = int(request.tg_user["id"])
    body = request.get_json(silent=True) or {}
    try:
        charge_id = int(body.get("charge_id"))
    except Exception:
        return jsonify({"ok": False, "error": "شناسه شارژ نامعتبر"}), 400
    ch = get_charge(charge_id)
    if not ch or int(ch.get("telegram_id") or 0) != user_id:
        return jsonify({"ok": False, "error": "درخواست شارژ یافت نشد"}), 404
    photo_b64 = body.get("photo") or ""
    if not photo_b64:
        return jsonify({"ok": False, "error": "تصویر رسید لازم است"}), 400
    try:
        from db_users import set_charge_receipt
        set_charge_receipt(charge_id, f"miniapp:{charge_id}")
    except Exception:
        pass
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE charge_requests SET status='pending_review' WHERE id=%s", (charge_id,))
            conn.commit()
    finally:
        conn.close()
    amount = int(ch.get("amount") or 0)
    # auto-approve check
    auto_done = _try_auto_approve_charge(charge_id, user_id, amount)
    if auto_done:
        _notify_user(user_id, f"شارژ #{charge_id} به صورت خودکار تایید شد.")
        return jsonify({"ok": True, "message": "رسید ثبت و به صورت خودکار تایید شد.", "auto_approved": True})
    if ADMIN_ID:
        kb = {"inline_keyboard": [[
            {"text": "تایید", "callback_data": f"adm_ch_ok_{charge_id}"},
            {"text": "رد", "callback_data": f"adm_ch_no_{charge_id}"},
        ]]}
        _tg_api("sendMessage", {
            "chat_id": ADMIN_ID,
            "text": "رسید شارژ #%s (مینی اپ)\nکاربر: %s\nمبلغ: %s تومان" % (charge_id, user_id, f"{amount:,}"),
            "reply_markup": kb,
        })
        try:
            import io
            raw = base64.b64decode(photo_b64.split(",")[-1] if "," in photo_b64 else photo_b64)
            _tg_api("sendPhoto", {"chat_id": str(ADMIN_ID), "caption": "رسید شارژ #%s" % charge_id},
                    files={"photo": ("receipt.jpg", io.BytesIO(raw), "image/jpeg")})
        except Exception as e:
            print("charge photo:", e)
    _notify_user(user_id, f"رسید شارژ #{charge_id} ثبت شد و در انتظار تایید است.")
    return jsonify({"ok": True, "message": "رسید شارژ ثبت شد."})


def _auto_approve_user_ids():
    from database import get_setting_sync
    raw = (get_setting_sync("card_auto_approve_users", "") or "").strip()
    ids = set()
    for part in raw.replace(" ", "").split(","):
        if part.isdigit():
            ids.add(int(part))
    return ids


def _try_auto_approve_charge(charge_id, user_id, amount):
    """Immediate auto-approve if user is in whitelist."""
    if int(user_id) not in _auto_approve_user_ids():
        return False
    try:
        from db_users import approve_charge
        approve_charge(charge_id)
        return True
    except Exception:
        try:
            from db_users import add_balance, get_charge
            from database import get_sync_connection
            ch = get_charge(charge_id)
            if not ch:
                return False
            add_balance(int(ch["telegram_id"]), int(ch["amount"]), f"charge#{charge_id}")
            conn = get_sync_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE charge_requests SET status='approved' WHERE id=%s", (charge_id,))
                    conn.commit()
            finally:
                conn.close()
            return True
        except Exception as e:
            print("auto approve charge:", e)
            return False


def _try_auto_approve_order(order_id, user_id):
    if int(user_id) not in _auto_approve_user_ids():
        return False
    try:
        from db_products import update_order
        update_order(order_id, status="paid")
        result = provision_order(order_id)
        if result.get("ok"):
            try:
                from db_products import get_order
                from db_growth import award_purchase_points
                o = get_order(order_id) or {}
                award_purchase_points(user_id, int(o.get("amount") or 0), order_id)
            except Exception as e:
                print("auto order points:", e)
        return bool(result.get("ok"))
    except Exception as e:
        print("auto approve order:", e)
        return False


@miniapp_bp.get("/api/trial/status")
@auth_required
def trial_status():
    from database import get_setting_sync
    user_id = int(request.tg_user["id"])
    enabled = get_setting_sync("trial_enabled", "0") == "1"
    used = False
    try:
        from db_growth import has_used_trial
        used = bool(has_used_trial(user_id))
    except Exception:
        used = False
    return jsonify({"ok": True, "enabled": enabled, "used": used, "available": enabled and not used})


@miniapp_bp.post("/api/trial/claim")
@auth_required
def trial_claim():
    from database import get_setting_sync, list_panels
    from db_growth import has_used_trial, record_trial
    from db_products import create_order, update_order
    user_id = int(request.tg_user["id"])
    if get_setting_sync("trial_enabled", "0") != "1":
        return jsonify({"ok": False, "error": "تست رایگان فعلا غیرفعال است."}), 400
    if has_used_trial(user_id):
        return jsonify({"ok": False, "error": "شما قبلا از تست رایگان استفاده کرده اید."}), 400
    body = request.get_json(silent=True) or {}
    panel_id = body.get("panel_id")
    raw = get_setting_sync("trial_panel_ids", "") or get_setting_sync("trial_panel_id", "")
    panels = list_panels() or []
    active = [p for p in panels if p.get("is_active", 1)]
    if raw.strip():
        ids = {int(x) for x in raw.replace(" ", "").split(",") if x.isdigit()}
        active = [p for p in active if p["id"] in ids] or active
    if not active:
        return jsonify({"ok": False, "error": "پنل تست تنظیم نشده."}), 400
    if panel_id:
        try:
            panel_id = int(panel_id)
        except Exception:
            return jsonify({"ok": False, "error": "پنل نامعتبر"}), 400
        if panel_id not in [p["id"] for p in active]:
            return jsonify({"ok": False, "error": "این پنل برای تست مجاز نیست"}), 400
    else:
        panel_id = active[0]["id"]
    vol = float(get_setting_sync("trial_volume_gb", "1") or 1)
    days = int(get_setting_sync("trial_days", "1") or 1)
    order_id = create_order(user_id, 1, panel_id, 0, 0, 0)
    # پروتکل‌های تست از تنظیمات (per-panel JSON)
    protocol_override = None
    try:
        import json
        raw = get_setting_sync("trial_protocols_json", "") or "{}"
        all_cfg = json.loads(raw) if raw else {}
        cfg = all_cfg.get(str(panel_id)) or all_cfg.get(panel_id) or {}
        if cfg and (cfg.get("inbound_ids") or cfg.get("group_ids")):
            protocol_override = json.dumps(cfg, ensure_ascii=False)
    except Exception as e:
        print("trial protocol cfg:", e)
    update_kwargs = dict(
        status="paid", wallet_used=0, pay_amount=0,
        volume_gb_override=vol, duration_days_override=days, custom_name="تست رایگان",
    )
    if protocol_override:
        update_kwargs["protocol_override"] = protocol_override
    update_order(order_id, **update_kwargs)
    result = provision_order(order_id)
    if not result.get("ok"):
        return jsonify({"ok": False, "error": result.get("error") or "ساخت تست ناموفق"}), 502
    try:
        record_trial(user_id)
    except Exception as e:
        print("record_trial", e)
    _notify_user(user_id, "تست رایگان شما فعال شد.")
    return jsonify({"ok": True, "message": "تست رایگان فعال شد.", "order_id": order_id, "provision": _jsonable(result)})


@miniapp_bp.post("/api/subscriptions/<int:order_id>/delete")
@auth_required
def subscription_delete(order_id):
    """Request delete+refund: disable service, notify admin for final delete/refund."""
    from db_products import update_order
    from config import ADMIN_ID
    user_id = int(request.tg_user["id"])
    o = get_user_order(order_id, user_id)
    if not o:
        return jsonify({"ok": False, "error": "سرویس پیدا نشد"}), 404
    body = request.get_json(silent=True) or {}
    if not bool(body.get("confirm")):
        return jsonify({"ok": False, "error": "تایید حذف لازم است"}), 400
    try:
        from database import get_panel_by_id
        from services.panel_client import get_panel_client
        panel = get_panel_by_id(o.get("panel_id")) if o.get("panel_id") else None
        if panel and o.get("vpn_username"):
            client = get_panel_client(panel)
            if client and hasattr(client, "modify_user"):
                client.modify_user(o["vpn_username"], {"status": "disabled"})
    except Exception as e:
        print("disable on delete request:", e)
    try:
        update_order(order_id, status="refund_requested")
    except Exception:
        conn = get_sync_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE service_orders SET status=%s WHERE id=%s AND telegram_id=%s",
                    ("refund_requested", order_id, user_id),
                )
                conn.commit()
        finally:
            conn.close()
    amount = int(o.get("amount") or 0)
    kb = {"inline_keyboard": [[
        {"text": "تایید حذف و بازگشت وجه", "callback_data": "adm_ref_ok_%s" % order_id},
        {"text": "رد درخواست", "callback_data": "adm_ref_no_%s" % order_id},
    ]]}
    text = (
        "درخواست حذف سرویس #%s\nکاربر: %s\nمبلغ قابل بازگشت: %s تومان\n"
        "سرویس فعلا غیرفعال شد. با تایید، حذف کامل و بازگشت وجه انجام میشود."
    ) % (order_id, user_id, f"{amount:,}")
    try:
        from db_extras import list_bot_admins
        admin_ids = [int(a["telegram_id"]) for a in list_bot_admins()]
    except Exception:
        admin_ids = []
    if ADMIN_ID:
        admin_ids = [int(ADMIN_ID)] + [x for x in admin_ids if int(x) != int(ADMIN_ID)]
    for admin_id in admin_ids:
        _tg_api("sendMessage", {"chat_id": admin_id, "text": text, "reply_markup": kb})
    _notify_user(
        user_id,
        "درخواست حذف سرویس #%s ثبت شد. پس از تایید ادمین، حذف و بازگشت وجه انجام میشود." % order_id,
    )
    return jsonify({"ok": True, "message": "درخواست حذف ثبت شد و برای تایید ادمین ارسال شد."})



@miniapp_bp.post("/api/loyalty/redeem")
@auth_required
def loyalty_redeem():
    """Redeem club package as gift VPN (panel + volume + days + hwid)."""
    user_id = int(request.tg_user["id"])
    body = request.get_json(silent=True) or {}
    pkg_id = str(body.get("package_id") or "")
    cfg = get_loyalty_config()
    packages = cfg.get("packages") or []
    pkg = next((x for x in packages if str(x.get("id")) == pkg_id), None)
    if not pkg:
        return jsonify({"ok": False, "error": "بسته یافت نشد"}), 404
    cost = int(pkg.get("points_cost") or 0)
    if cost <= 0:
        return jsonify({"ok": False, "error": "بسته نامعتبر"}), 400
    min_level = (pkg.get("min_level") or "").strip()
    loy = _loyalty(user_id)
    if min_level:
        levels = sorted(cfg.get("levels") or [], key=lambda x: int(x.get("min_points") or 0))
        order = {lv.get("name"): i for i, lv in enumerate(levels)}
        if order.get(loy.get("level"), -1) < order.get(min_level, 0):
            return jsonify({"ok": False, "error": "حداقل سطح لازم: %s" % min_level}), 400

    panel_id = pkg.get("panel_id")
    volume_gb = float(pkg.get("volume_gb") or 0)
    duration_days = int(pkg.get("duration_days") or 0)
    hwid_limit = int(pkg.get("hwid_limit") or 0)
    if not panel_id or duration_days <= 0:
        return jsonify({"ok": False, "error": "تنظیمات بسته VPN ناقص است (پنل/مدت)."}), 400

    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT points FROM loyalty_accounts WHERE telegram_id=%s FOR UPDATE", (user_id,))
            row = cur.fetchone()
            pts = int((row or {}).get("points") or 0)
            if pts < cost:
                return jsonify({"ok": False, "error": "امتیاز کافی نیست", "points": pts, "required": cost}), 402
            cur.execute("UPDATE loyalty_accounts SET points=points-%s WHERE telegram_id=%s", (cost, user_id))
            cur.execute(
                """INSERT INTO loyalty_transactions
                   (telegram_id,points,type,reference_id,description)
                   VALUES (%s,%s,'redeem',%s,%s)""",
                (user_id, -cost, pkg_id, "دریافت بسته: %s" % (pkg.get("title") or pkg_id)),
            )
            conn.commit()
    finally:
        conn.close()

    order_id = None
    provision = None
    try:
        from db_products import create_order, update_order
        product_id = int(pkg.get("product_id") or 0) or 1
        order_id = create_order(user_id, product_id, int(panel_id), 0, 0, 0)
        update_order(
            order_id,
            status="paid",
            wallet_used=0,
            pay_amount=0,
            volume_gb_override=volume_gb if volume_gb > 0 else None,
            duration_days_override=duration_days,
            custom_name=(pkg.get("title") or "هدیه باشگاه")[:80],
        )
        provision = provision_order(order_id)
        if provision.get("ok") and hwid_limit > 0:
            try:
                from services.service_edit import edit_sold_service
                edit_sold_service(order_id, hwid_limit=hwid_limit)
            except Exception as e:
                print("gift hwid:", e)
        if not provision.get("ok"):
            conn = get_sync_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE loyalty_accounts SET points=points+%s WHERE telegram_id=%s", (cost, user_id))
                    conn.commit()
            finally:
                conn.close()
            return jsonify({"ok": False, "error": provision.get("error") or "ساخت سرویس هدیه ناموفق"}), 502
        _notify_user(user_id, "هدیه باشگاه فعال شد: %s" % (pkg.get("title") or ""))
    except Exception as e:
        print("loyalty vpn gift:", e)
        conn = get_sync_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE loyalty_accounts SET points=points+%s WHERE telegram_id=%s", (cost, user_id))
                conn.commit()
        finally:
            conn.close()
        return jsonify({"ok": False, "error": "خطا در ساخت هدیه: %s" % e}), 500

    return jsonify({
        "ok": True,
        "message": "بسته با موفقیت دریافت شد.",
        "points_spent": cost,
        "order_id": order_id,
        "provision": _jsonable(provision or {}),
    })


@miniapp_bp.errorhandler(Exception)
def miniapp_error(error):
    print("Mini App error:", error)
    return jsonify({"ok": False, "error": "خطای غیرمنتظره‌ای رخ داد."}), 500
