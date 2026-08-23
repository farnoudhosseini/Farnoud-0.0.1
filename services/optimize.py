# بهینه‌سازی دیتابیس ربات — حذف سفارش‌های لغو/منقضی قدیمی و لاگ‌های اضافی

from __future__ import annotations
from database import get_sync_connection


def optimize_bot_data(days_cancelled: int = 7, days_logs: int = 30) -> dict:
    """
    - سفارش‌های cancelled / expired قدیمی
    - لاگ فعالیت قدیمی
    - سفارش‌های pending قدیمی بدون پرداخت
    """
    stats = {"orders_cancelled": 0, "orders_pending": 0, "activity_logs": 0, "errors": []}
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            try:
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
                    """DELETE FROM service_orders
                       WHERE status IN ('pending','waiting_receipt','pending_review')
                         AND created_at < (NOW() - INTERVAL %s DAY)""",
                    (max(int(days_cancelled), 14),),
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
        f"• سفارش‌های معلق قدیمی: <b>{stats.get('orders_pending', 0)}</b>",
        f"• لاگ‌های قدیمی: <b>{stats.get('activity_logs', 0)}</b>",
    ]
    if stats.get("errors"):
        lines.append("⚠️ هشدارها:")
        for e in stats["errors"][:5]:
            lines.append(f"• <code>{e}</code>")
    return "\n".join(lines)
