# بهینه‌سازی دیتابیس ربات — حذف سفارش‌های لغو/منقضی قدیمی از ربات و پنل‌ها

from __future__ import annotations
from database import get_sync_connection


def _delete_from_panel(order: dict) -> bool:
    """حذف کاربر سرویس از پنل (پاسارگارد / سنایی / 3x-ui). تلاش چندگانه برای اطمینان از حذف."""
    uname = (order.get("vpn_username") or "").strip()
    if not uname:
        return False
    try:
        from services.panel_client import get_panel_client
        from database import get_panel_by_id
        panel = None
        if order.get("panel_id"):
            try:
                panel = get_panel_by_id(int(order["panel_id"]))
            except Exception:
                panel = None
        if not panel or not (panel.get("base_url") or panel.get("username")):
            panel = {
                "id": order.get("panel_id"),
                "base_url": order.get("panel_base") or order.get("base_url"),
                "username": order.get("panel_user"),
                "password": order.get("panel_pass"),
                "panel_type": order.get("panel_type"),
                "api_key": order.get("api_key"),
            }
        if not panel.get("base_url"):
            return False
        client = get_panel_client(panel)
        if not client:
            return False
        deleted = False
        # اول delete_user (پاسارگارد و xui3 هر دو دارند)
        if hasattr(client, "delete_user"):
            try:
                client.delete_user(uname)
                deleted = True
            except Exception as e:
                print(f"optimize delete_user {uname}:", e)
        # اگر inbound مشخص است، delete_client هم امتحان کن
        if hasattr(client, "delete_client") and order.get("inbound_id"):
            try:
                client.delete_client(int(order["inbound_id"]), uname)
                deleted = True
            except Exception as e:
                print(f"optimize delete_client {uname}:", e)
        return deleted
    except Exception as e:
        print(f"optimize panel delete {uname}:", e)
    return False


def _is_trial_order(o: dict) -> bool:
    """تشخیص سفارش تست رایگان."""
    cname = (o.get("custom_name") or "").strip().lower()
    if cname and any(x in cname for x in ("تست", "trial", "رایگان", "free")):
        return True
    try:
        if float(o.get("amount") or 0) == 0 and o.get("volume_gb_override") is not None:
            return True
    except Exception:
        pass
    return False


def _is_missing_user_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return ("404" in msg and ("user" in msg or "not found" in msg or "یافت" in msg)) or "user not found" in msg


def _mark_order_expired(cur, order_id: int) -> bool:
    try:
        cur.execute("UPDATE service_orders SET status='expired', admin_note=CONCAT(COALESCE(admin_note,''), %s) WHERE id=%s", ("\n[auto-sync] کاربر از پنل حذف شده است.", int(order_id)))
        return True
    except Exception as e:
        print("mark expired:", e)
        return False


def optimize_bot_data(days_cancelled: int = 7, days_logs: int = 30) -> dict:
    """
    - سفارش‌های cancelled / expired قدیمی + حذف از پنل
    - سرویس‌های provisioned/paid منقضی‌شده که تمدید نشده‌اند + حذف از پنل
    - تست‌های رایگان منقضی: حذف از پنل و مخفی از سرویس‌های من، ولی در دیتابیس می‌مانند
    - لاگ فعالیت قدیمی
    - سفارش‌های pending قدیمی بدون پرداخت
    """
    stats = {
        "orders_cancelled": 0,
        "orders_pending": 0,
        "orders_expired_live": 0,
        "panel_deleted": 0,
        "activity_logs": 0,
        "expired_trials": 0,
        "unused_trials": 0,
        "errors": [],
    }
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """SELECT id, vpn_username, panel_id, inbound_id, custom_name, amount,
                              volume_gb_override
                       FROM service_orders
                       WHERE status IN ('cancelled','canceled','expired','failed')
                         AND created_at < (NOW() - INTERVAL %s DAY)""",
                    (int(days_cancelled),),
                )
                rows = cur.fetchall() or []
                for o in rows:
                    # تست‌ها را از دیتابیس پاک نکن — فقط از پنل حذف
                    if _is_trial_order(o):
                        if _delete_from_panel(o):
                            stats["panel_deleted"] += 1
                        continue
                    if _delete_from_panel(o):
                        stats["panel_deleted"] += 1
                cur.execute(
                    """DELETE FROM service_orders
                       WHERE status IN ('cancelled','canceled','expired','failed')
                         AND created_at < (NOW() - INTERVAL %s DAY)
                         AND NOT (
                           (custom_name IS NOT NULL AND (
                             custom_name LIKE %s OR custom_name LIKE %s OR custom_name LIKE %s OR custom_name LIKE %s
                           ))
                           OR (COALESCE(amount,0)=0 AND volume_gb_override IS NOT NULL)
                         )""",
                    (int(days_cancelled), "%تست%", "%trial%", "%رایگان%", "%free%"),
                )
                stats["orders_cancelled"] = cur.rowcount or 0
            except Exception as e:
                stats["errors"].append(f"orders_cancelled: {e}")

            try:
                cur.execute(
                    """SELECT o.id, o.vpn_username, o.panel_id, o.inbound_id,
                              o.expire_at, o.custom_name, o.amount, o.volume_gb_override,
                              vp.base_url AS panel_base, vp.username AS panel_user,
                              vp.password AS panel_pass, vp.panel_type, vp.api_key
                       FROM service_orders o
                       LEFT JOIN vpn_panels vp ON vp.id = o.panel_id
                       WHERE o.status IN ('paid','provisioned')
                         AND o.expire_at IS NOT NULL
                         AND o.expire_at < NOW()
                         AND (o.is_hourly IS NULL OR o.is_hourly = 0 OR o.hourly_active = 0)"""
                )
                expired_live = cur.fetchall() or []
                for o in expired_live:
                    if _delete_from_panel(o):
                        stats["panel_deleted"] += 1
                    try:
                        cur.execute(
                            "UPDATE service_orders SET status='expired' WHERE id=%s",
                            (o["id"],),
                        )
                    except Exception:
                        pass
                    if _is_trial_order(o):
                        stats["expired_trials"] += 1
                # سفارش‌های غیرتست expired قدیمی را حذف کن؛ تست‌ها در DB بمانند
                cur.execute(
                    """DELETE FROM service_orders
                       WHERE status = 'expired'
                         AND expire_at IS NOT NULL
                         AND expire_at < (NOW() - INTERVAL %s DAY)
                         AND NOT (
                           (custom_name IS NOT NULL AND (
                             custom_name LIKE %s OR custom_name LIKE %s OR custom_name LIKE %s OR custom_name LIKE %s
                           ))
                           OR (COALESCE(amount,0)=0 AND volume_gb_override IS NOT NULL)
                         )""",
                    (int(days_cancelled), "%تست%", "%trial%", "%رایگان%", "%free%"),
                )
                stats["orders_expired_live"] = len(expired_live)
            except Exception as e:
                stats["errors"].append(f"orders_expired_live: {e}")

            # سرویس‌های اتمام حجم (هنوز expire_at نرسیده ولی ترافیک تمام شده)
            try:
                cur.execute(
                    """SELECT o.id, o.vpn_username, o.panel_id, o.inbound_id,
                              o.custom_name, o.amount, o.volume_gb_override,
                              o.product_id, p.volume_gb AS product_volume,
                              vp.base_url AS panel_base, vp.username AS panel_user,
                              vp.password AS panel_pass, vp.panel_type, vp.api_key
                       FROM service_orders o
                       LEFT JOIN products p ON p.id = o.product_id
                       LEFT JOIN vpn_panels vp ON vp.id = o.panel_id
                       WHERE o.status IN ('paid','provisioned')
                         AND o.vpn_username IS NOT NULL AND o.vpn_username != ''
                         AND (o.is_hourly IS NULL OR o.is_hourly = 0 OR o.hourly_active = 0)"""
                )
                live_orders = cur.fetchall() or []
                vol_exhausted = 0
                for o in live_orders:
                    if _is_trial_order(o):
                        continue  # تست‌ها جدا هندل می‌شوند
                    uname = (o.get("vpn_username") or "").strip()
                    if not uname:
                        continue
                    try:
                        from services.panel_client import get_panel_client
                        from database import get_panel_by_id
                        panel = get_panel_by_id(int(o["panel_id"])) if o.get("panel_id") else None
                        if not panel:
                            panel = {
                                "base_url": o.get("panel_base"),
                                "username": o.get("panel_user"),
                                "password": o.get("panel_pass"),
                                "panel_type": o.get("panel_type"),
                                "api_key": o.get("api_key"),
                            }
                        client = get_panel_client(panel) if panel and panel.get("base_url") else None
                        if not client:
                            continue
                        full = {}
                        if hasattr(client, "get_user"):
                            full = client.get_user(uname) or {}
                        elif hasattr(client, "get_client_traffics"):
                            full = client.get_client_traffics(uname) or {}
                        used = full.get("used_traffic")
                        if used is None:
                            used = (full.get("up") or 0) + (full.get("down") or 0)
                        try:
                            used = int(used or 0)
                        except Exception:
                            used = 0
                        # حجم مجاز به بایت
                        limit_gb = o.get("volume_gb_override") or o.get("volume_gb") or o.get("product_volume") or 0
                        try:
                            limit_gb = float(limit_gb or 0)
                        except Exception:
                            limit_gb = 0
                        if limit_gb <= 0:
                            continue
                        limit_bytes = int(limit_gb * 1024 * 1024 * 1024)
                        # اگر بیش از ۹۵٪ حجم مصرف شده یا پنل خودش disabled کرده
                        st = (full.get("status") or "").lower()
                        if used >= limit_bytes * 0.95 or st in ("disabled", "expired", "limited"):
                            if _delete_from_panel(o):
                                stats["panel_deleted"] += 1
                            cur.execute(
                                "UPDATE service_orders SET status='expired' WHERE id=%s",
                                (o["id"],),
                            )
                            vol_exhausted += 1
                    except Exception as e:
                        if _is_missing_user_error(e):
                            if _mark_order_expired(cur, o["id"]):
                                stats["volume_exhausted"] = stats.get("volume_exhausted", 0)
                            continue
                        stats["errors"].append(f"vol_check {uname}: {e}")
                stats["volume_exhausted"] = vol_exhausted
            except Exception as e:
                stats["errors"].append(f"volume_exhausted: {e}")

            try:
                # سفارش‌های پرداخت‌نشده / منتظر رسید — حذف از لیست (بازه کوتاه‌تر)
                cur.execute(
                    """DELETE FROM service_orders
                       WHERE status IN (
                         'pending','pending_payment','waiting_receipt','pending_review',
                         'waiting_pay','unpaid','draft'
                       )
                         AND created_at < (NOW() - INTERVAL %s DAY)""",
                    (max(int(days_cancelled), 1),),
                )
                stats["orders_pending"] = cur.rowcount or 0
            except Exception as e:
                stats["errors"].append(f"orders_pending: {e}")

            for table in ("user_activity", "activity_logs", "bot_activity", "logs"):
                try:
                    cur.execute(
                        f"DELETE FROM `{table}` WHERE created_at < (NOW() - INTERVAL %s DAY)",
                        (int(days_logs),),
                    )
                    stats["activity_logs"] += cur.rowcount or 0
                except Exception:
                    pass

            # تست‌های رایگان استفاده‌نشده (ترافیک صفر): فقط حذف از پنل + status=expired — در DB بمانند
            try:
                cur.execute(
                    """SELECT o.id, o.vpn_username, o.panel_id, o.inbound_id, o.custom_name,
                              o.volume_gb_override, o.amount, o.status,
                              vp.base_url AS panel_base, vp.username AS panel_user,
                              vp.password AS panel_pass, vp.panel_type, vp.api_key
                       FROM service_orders o
                       LEFT JOIN vpn_panels vp ON vp.id = o.panel_id
                       WHERE o.status IN ('paid','provisioned')
                         AND (
                           (o.custom_name IS NOT NULL AND (o.custom_name LIKE %s OR o.custom_name LIKE %s OR o.custom_name LIKE %s OR o.custom_name LIKE %s))
                           OR (COALESCE(o.amount,0)=0 AND o.volume_gb_override IS NOT NULL)
                         )""",
                    ("%تست%", "%trial%", "%رایگان%", "%free%"),
                )
                trials = cur.fetchall() or []
                for o in trials:
                    uname = (o.get("vpn_username") or "").strip()
                    if not uname:
                        continue
                    used = None
                    try:
                        from services.panel_client import get_panel_client
                        from database import get_panel_by_id
                        panel = get_panel_by_id(int(o["panel_id"])) if o.get("panel_id") else None
                        if not panel:
                            panel = {
                                "id": o.get("panel_id"),
                                "base_url": o.get("panel_base"),
                                "username": o.get("panel_user"),
                                "password": o.get("panel_pass"),
                                "panel_type": o.get("panel_type"),
                                "api_key": o.get("api_key"),
                            }
                        client = get_panel_client(panel) if panel else None
                        if client and hasattr(client, "get_user"):
                            full = client.get_user(uname) or {}
                            used = full.get("used_traffic")
                            if used is None:
                                used = (full.get("up") or 0) + (full.get("down") or 0)
                            try:
                                used = int(used or 0)
                            except Exception:
                                used = 0
                        elif client and hasattr(client, "get_client_traffics"):
                            st = client.get_client_traffics(uname) or {}
                            used = int(st.get("used_traffic") or st.get("up", 0) + st.get("down", 0) or 0)
                    except Exception as e:
                        if _is_missing_user_error(e):
                            if _delete_from_panel(o):
                                stats["panel_deleted"] += 1
                            _mark_order_expired(cur, o["id"])
                            stats["expired_trials"] += 1
                            continue
                        stats["errors"].append(f"trial check {uname}: {e}")
                        continue
                    # فقط اگر واقعاً ترافیک صفر / وصل نشده
                    if used is not None and used <= 0:
                        if _delete_from_panel(o):
                            stats["panel_deleted"] += 1
                        try:
                            # در DB نگه دار تا کاربر نتواند دوباره تست بگیرد (trials table جداست)
                            # اما از سرویس‌های من حذف شود با status=expired
                            cur.execute(
                                "UPDATE service_orders SET status='expired' WHERE id=%s",
                                (o["id"],),
                            )
                            stats["unused_trials"] += 1
                        except Exception as e:
                            stats["errors"].append(f"trial expire {o.get('id')}: {e}")
            except Exception as e:
                stats["errors"].append(f"unused_trials: {e}")

            try:
                cur.execute("OPTIMIZE TABLE service_orders")
            except Exception:
                pass
            conn.commit()
    except Exception as e:
        stats["errors"].append(str(e))
    finally:
        conn.close()
    return stats


def format_optimize_report(stats: dict) -> str:
    lines = [
        "🧹 <b>بهینه‌سازی ربات انجام شد</b>",
        f"• سفارش‌های لغو/منقضی حذف‌شده: <b>{stats.get('orders_cancelled', 0)}</b>",
        f"• سرویس‌های منقضی (زنده): <b>{stats.get('orders_expired_live', 0)}</b>",
        f"• اتمام حجم: <b>{stats.get('volume_exhausted', 0)}</b>",
        f"• تست‌های منقضی (نگه‌داشته در DB): <b>{stats.get('expired_trials', 0)}</b>",
        f"• حذف از پنل: <b>{stats.get('panel_deleted', 0)}</b>",
        f"• سفارش‌های معلق قدیمی: <b>{stats.get('orders_pending', 0)}</b>",
        f"• لاگ‌های قدیمی: <b>{stats.get('activity_logs', 0)}</b>",
        f"• تست رایگان استفاده‌نشده: <b>{stats.get('unused_trials', 0)}</b>",
    ]
    errs = stats.get("errors") or []
    if errs:
        lines.append("⚠️ خطاها:")
        for e in errs[:5]:
            lines.append(f"• <code>{e}</code>")
    return "\n".join(lines)
