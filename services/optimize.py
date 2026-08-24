# بهینه‌سازی دیتابیس ربات — حذف سفارش‌های لغو/منقضی قدیمی از ربات و پنل‌ها

from __future__ import annotations
from database import get_sync_connection


def _delete_from_panel(order: dict) -> bool:
    """حذف کاربر سرویس از پنل (پاسارگارد / سنایی / 3x-ui)."""
    uname = (order.get("vpn_username") or "").strip()
    if not uname:
        return False
    try:
        from services.panel_client import get_panel_client
        from database import get_panel_by_id
        panel = None
        if order.get("panel_id"):
            panel = get_panel_by_id(int(order["panel_id"]))
        if not panel:
            panel = {
                "id": order.get("panel_id"),
                "base_url": order.get("panel_base") or order.get("base_url"),
                "username": order.get("panel_user"),
                "password": order.get("panel_pass"),
                "panel_type": order.get("panel_type"),
                "api_key": order.get("api_key"),
            }
        client = get_panel_client(panel) if panel else None
        if not client:
            return False
        if hasattr(client, "delete_user"):
            client.delete_user(uname)
            return True
        if hasattr(client, "delete_client") and order.get("inbound_id"):
            client.delete_client(int(order["inbound_id"]), uname)
            return True
    except Exception as e:
        print(f"optimize panel delete {uname}:", e)
    return False


def optimize_bot_data(days_cancelled: int = 7, days_logs: int = 30) -> dict:
    """
    - سفارش‌های cancelled / expired قدیمی + حذف از پنل
    - سرویس‌های provisioned/paid منقضی‌شده که تمدید نشده‌اند + حذف از پنل
    - لاگ فعالیت قدیمی
    - سفارش‌های pending قدیمی بدون پرداخت
    """
    stats = {
        "orders_cancelled": 0,
        "orders_pending": 0,
        "orders_expired_live": 0,
        "panel_deleted": 0,
        "activity_logs": 0,
        "errors": [],
    }
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """SELECT id, vpn_username, panel_id, inbound_id
                       FROM service_orders
                       WHERE status IN ('cancelled','canceled','expired','failed')
                         AND created_at < (NOW() - INTERVAL %s DAY)""",
                    (int(days_cancelled),),
                )
                rows = cur.fetchall() or []
                for o in rows:
                    if _delete_from_panel(o):
                        stats["panel_deleted"] += 1
                cur.execute(
                    """DELETE FROM service_orders
                       WHERE status IN ('cancelled','canceled','expired','failed')
                         AND created_at < (NOW() - INTERVAL %s DAY)""",
                    (int(days_cancelled),),
                )
                stats["orders_cancelled"] = cur.rowcount or 0
            except Exception as e:
                stats["errors"].append(f"orders_cancelled: {e}")

            try:
                cur.execute(
                    """SELECT o.id, o.vpn_username, o.panel_id, o.inbound_id,
                              o.expire_at, vp.base_url AS panel_base, vp.username AS panel_user,
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
                cur.execute(
                    """DELETE FROM service_orders
                       WHERE status = 'expired'
                         AND expire_at IS NOT NULL
                         AND expire_at < (NOW() - INTERVAL %s DAY)""",
                    (int(days_cancelled),),
                )
                stats["orders_expired_live"] = len(expired_live)
            except Exception as e:
                stats["errors"].append(f"orders_expired_live: {e}")

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

            # تست‌های رایگان استفاده‌نشده: حذف از پنل + لیست سرویس کاربر
            stats.setdefault("unused_trials", 0)
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
                           (o.custom_name IS NOT NULL AND (o.custom_name LIKE %s OR o.custom_name LIKE %s OR o.custom_name LIKE %s))
                           OR (COALESCE(o.amount,0)=0 AND o.volume_gb_override IS NOT NULL)
                         )""",
                    ("%تست%", "%trial%", "%رایگان%"),
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
                        stats["errors"].append(f"trial check {uname}: {e}")
                        continue
                    # فقط اگر واقعاً ترافیک صفر / وصل نشده
                    if used is not None and used <= 0:
                        if _delete_from_panel(o):
                            stats["panel_deleted"] += 1
                        try:
                            cur.execute("DELETE FROM service_orders WHERE id=%s", (o["id"],))
                            stats["unused_trials"] += 1
                        except Exception as e:
                            stats["errors"].append(f"trial delete {o.get('id')}: {e}")
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
