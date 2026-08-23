# سیستم آنتی‌اسپم قابل تنظیم — محدودیت نرخ + مسدودسازی موقت

from __future__ import annotations
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple

from telegram import Update
from telegram.ext import ContextTypes, TypeHandler, ApplicationHandlerStop

# user_id -> timestamps
_buckets: Dict[int, Deque[float]] = defaultdict(deque)
# user_id -> ban_until monotonic
_bans: Dict[int, float] = {}
# cache settings (refresh every 30s)
_settings_cache: Tuple[float, dict] = (0.0, {})


def _load_settings() -> dict:
    global _settings_cache
    now = time.monotonic()
    if now - _settings_cache[0] < 30:
        return _settings_cache[1]
    defaults = {
        "enabled": True,
        "max_hits": 8,
        "window_sec": 5.0,
        "ban_sec": 300,  # 5 minutes
        "admins_exempt": True,
        "message": "به دلیل ارسال بیش از حد، تا ۵ دقیقه امکان ارسال پیام ندارید.",
    }
    try:
        from database import get_setting_sync
        enabled = get_setting_sync("antispam_enabled", "1") != "0"
        max_hits = int(get_setting_sync("antispam_max_hits", "8") or 8)
        window_sec = float(get_setting_sync("antispam_window_sec", "5") or 5)
        ban_sec = int(get_setting_sync("antispam_ban_sec", "300") or 300)
        admins_exempt = get_setting_sync("antispam_admins_exempt", "1") != "0"
        message = get_setting_sync("antispam_message", "") or defaults["message"]
        cfg = {
            "enabled": enabled,
            "max_hits": max(1, max_hits),
            "window_sec": max(1.0, window_sec),
            "ban_sec": max(30, ban_sec),
            "admins_exempt": admins_exempt,
            "message": message,
        }
    except Exception:
        cfg = defaults
    _settings_cache = (now, cfg)
    return cfg


def clear_ban(user_id: int):
    _bans.pop(int(user_id), None)
    _buckets.pop(int(user_id), None)


def is_temporarily_banned(user_id: int) -> Tuple[bool, int]:
    """Returns (banned, remaining_seconds)."""
    until = _bans.get(int(user_id))
    if not until:
        return False, 0
    now = time.monotonic()
    if now >= until:
        _bans.pop(int(user_id), None)
        return False, 0
    return True, int(until - now)


def _is_admin(user_id: int) -> bool:
    try:
        from config import ADMIN_ID
        if ADMIN_ID and int(user_id) == int(ADMIN_ID):
            return True
    except Exception:
        pass
    try:
        from db_extras import is_bot_admin
        return bool(is_bot_admin(int(user_id)))
    except Exception:
        return False


def _register_hit(user_id: int, cfg: dict) -> bool:
    """Return True if this hit exceeds limit (should ban)."""
    now = time.monotonic()
    q = _buckets[user_id]
    window = cfg["window_sec"]
    while q and now - q[0] > window:
        q.popleft()
    q.append(now)
    return len(q) > cfg["max_hits"]


async def antispam_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    cfg = _load_settings()
    if not cfg.get("enabled"):
        return
    uid = int(user.id)
    if cfg.get("admins_exempt") and _is_admin(uid):
        return

    # permanent block from DB
    try:
        from db_users import get_bot_user
        bu = get_bot_user(uid)
        if bu and bu.get("is_blocked"):
            if update.message:
                try:
                    await update.message.reply_text("دسترسی شما مسدود است.")
                except Exception:
                    pass
            raise ApplicationHandlerStop()
    except ApplicationHandlerStop:
        raise
    except Exception:
        pass

    banned, remain = is_temporarily_banned(uid)
    if banned:
        if update.message:
            try:
                mins = max(1, (remain + 59) // 60)
                await update.message.reply_text(
                    (cfg.get("message") or "محدود شده‌اید.") + f"\nمانده حدوداً: {mins} دقیقه"
                )
            except Exception:
                pass
        elif update.callback_query:
            try:
                await update.callback_query.answer("محدودیت ارسال فعال است. کمی صبر کنید.", show_alert=True)
            except Exception:
                pass
        raise ApplicationHandlerStop()

    if _register_hit(uid, cfg):
        _bans[uid] = time.monotonic() + cfg["ban_sec"]
        _buckets[uid].clear()
        if update.message:
            try:
                await update.message.reply_text(cfg.get("message") or "محدود شدید.")
            except Exception:
                pass
        elif update.callback_query:
            try:
                await update.callback_query.answer("به دلیل اسپم موقتاً محدود شدید.", show_alert=True)
            except Exception:
                pass
        raise ApplicationHandlerStop()


def install_antispam(application):
    application.add_handler(TypeHandler(Update, antispam_handler), group=-1)
