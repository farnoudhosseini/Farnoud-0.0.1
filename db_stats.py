# آمار داشبورد

from database import get_sync_connection

def dashboard_counts():
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            def one(sql):
                try:
                    cur.execute(sql)
                    r = cur.fetchone() or {}
                    return int(list(r.values())[0] or 0)
                except Exception:
                    return 0
            return {
                "users": one("SELECT COUNT(*) AS c FROM bot_users"),
                "orders": one("SELECT COUNT(*) AS c FROM service_orders WHERE status IN ('paid','provisioned')"),
                "revenue": one("SELECT COALESCE(SUM(amount),0) AS c FROM service_orders WHERE status IN ('paid','provisioned')"),
                "pending_charges": one("SELECT COUNT(*) AS c FROM charge_requests WHERE status='pending_review'"),
                "panels": one("SELECT COUNT(*) AS c FROM vpn_panels"),
                "products": one("SELECT COUNT(*) AS c FROM products WHERE is_active=1"),
                "open_tickets": one("SELECT COUNT(*) AS c FROM support_tickets WHERE status!='closed'"),
            }
    finally:
        conn.close()

def chart_series(period: str = "7"):
    """period: today | 7 | 28 | all"""
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            if period == "today":
                days = 1
            elif period == "28":
                days = 28
            elif period == "all":
                days = 90
            else:
                days = 7

            # users per day
            cur.execute(
                """
                SELECT DATE(created_at) AS d, COUNT(*) AS c
                FROM bot_users
                WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                GROUP BY DATE(created_at)
                ORDER BY d
                """,
                (days - 1,),
            )
            users = {str(r["d"]): int(r["c"]) for r in (cur.fetchall() or [])}

            cur.execute(
                """
                SELECT DATE(created_at) AS d, COUNT(*) AS orders, COALESCE(SUM(amount),0) AS revenue
                FROM service_orders
                WHERE status IN ('paid','provisioned')
                  AND created_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                GROUP BY DATE(created_at)
                ORDER BY d
                """,
                (days - 1,),
            )
            sales = {str(r["d"]): {"orders": int(r["orders"]), "revenue": float(r["revenue"])} for r in (cur.fetchall() or [])}

            from datetime import date, timedelta
            labels, u_data, o_data, rev_data = [], [], [], []
            start = date.today() - timedelta(days=days - 1)
            for i in range(days):
                d = start + timedelta(days=i)
                key = str(d)
                labels.append(key[5:])  # MM-DD
                u_data.append(users.get(key, 0))
                o_data.append(sales.get(key, {}).get("orders", 0))
                rev_data.append(sales.get(key, {}).get("revenue", 0))

            return {
                "labels": labels,
                "users": u_data,
                "orders": o_data,
                "revenue": rev_data,
                "users_total": sum(u_data),
                "orders_total": sum(o_data),
                "revenue_total": sum(rev_data),
            }
    finally:
        conn.close()


def _one(cur, sql, params=None):
    try:
        cur.execute(sql, params or ())
        r = cur.fetchone() or {}
        vals = list(r.values())
        return vals[0] if vals else 0
    except Exception:
        return 0


def bot_full_stats() -> dict:
    """آمار کامل برای پنل مدیریت ربات."""
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            total_users = int(_one(cur, "SELECT COUNT(*) AS c FROM bot_users") or 0)
            buyers = int(_one(cur, """
                SELECT COUNT(DISTINCT telegram_id) AS c FROM service_orders
                WHERE status IN ('paid','provisioned')
            """) or 0)
            trials = int(_one(cur, """
                SELECT COUNT(*) AS c FROM service_orders
                WHERE (amount IS NULL OR amount=0)
                  AND status IN ('paid','provisioned')
            """) or 0)
            # fallback trial by product name
            if trials == 0:
                trials = int(_one(cur, """
                    SELECT COUNT(*) AS c FROM service_orders o
                    LEFT JOIN products p ON p.id=o.product_id
                    WHERE o.status IN ('paid','provisioned')
                      AND (p.name LIKE '%تست%' OR p.name LIKE '%trial%' OR p.is_trial=1)
                """) or 0)
            total_balance = float(_one(cur, "SELECT COALESCE(SUM(balance),0) AS c FROM bot_users") or 0)
            total_sales = int(_one(cur, """
                SELECT COUNT(*) AS c FROM service_orders WHERE status IN ('paid','provisioned') AND COALESCE(amount,0)>0
            """) or 0)
            active_sales = int(_one(cur, """
                SELECT COUNT(*) AS c FROM service_orders
                WHERE status IN ('paid','provisioned')
                  AND (vpn_status IS NULL OR vpn_status IN ('active','on_hold') OR vpn_status='')
                  AND COALESCE(amount,0)>0
            """) or 0)
            sum_sales = float(_one(cur, """
                SELECT COALESCE(SUM(amount),0) AS c FROM service_orders
                WHERE status IN ('paid','provisioned') AND COALESCE(amount,0)>0
            """) or 0)
            sum_active = float(_one(cur, """
                SELECT COALESCE(SUM(amount),0) AS c FROM service_orders
                WHERE status IN ('paid','provisioned')
                  AND (vpn_status IS NULL OR vpn_status IN ('active','on_hold') OR vpn_status='')
                  AND COALESCE(amount,0)>0
            """) or 0)
            sum_renew = float(_one(cur, """
                SELECT COALESCE(SUM(amount),0) AS c FROM service_orders
                WHERE status IN ('paid','provisioned')
                  AND (is_renewal=1 OR parent_order_id IS NOT NULL OR note LIKE '%تمدید%')
            """) or 0)
            resellers = int(_one(cur, "SELECT COUNT(*) AS c FROM bot_users WHERE role='reseller'") or 0)
            resellers_vip = int(_one(cur, "SELECT COUNT(*) AS c FROM bot_users WHERE role='reseller_vip'") or 0)
            panels = int(_one(cur, "SELECT COUNT(*) AS c FROM vpn_panels") or 0)
            pay_ok = int(_one(cur, """
                SELECT COUNT(*) AS c FROM charge_requests WHERE status='approved'
            """) or 0)
            pay_sum = float(_one(cur, """
                SELECT COALESCE(SUM(amount),0) AS c FROM charge_requests WHERE status='approved'
            """) or 0)
            gateway = "کارت به کارت"
            try:
                cur.execute("SELECT title FROM payment_methods WHERE is_active=1 ORDER BY id LIMIT 1")
                row = cur.fetchone()
                if row:
                    gateway = row.get("title") or gateway
            except Exception:
                pass

            conv = (buyers / total_users * 100) if total_users else 0.0
            avg_buy = (sum_sales / buyers) if buyers else 0.0
            renew_pct = (sum_renew / sum_sales * 100) if sum_sales else 0.0

            return {
                "total_users": total_users,
                "buyers": buyers,
                "trials": trials,
                "total_balance": int(total_balance),
                "total_sales": total_sales,
                "active_sales": active_sales,
                "sum_sales": int(sum_sales),
                "sum_active": int(sum_active),
                "sum_renew": int(sum_renew),
                "conversion": conv,
                "avg_buy": int(avg_buy),
                "forecast_month": 0,
                "renew_pct": renew_pct,
                "resellers": resellers,
                "resellers_vip": resellers_vip,
                "panels": panels,
                "gateway": gateway,
                "pay_ok": pay_ok,
                "pay_sum": int(pay_sum),
            }
    finally:
        conn.close()


def format_bot_stats_text(stats: dict, ping_ms: int = 0) -> str:
    def n(v):
        try:
            return f"{int(v):,}"
        except Exception:
            return str(v)

    return (
        "📊 <b>آمار کلی ربات</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👥 تعداد کل کاربران: <b>{n(stats.get('total_users'))}</b> نفر\n"
        f"🛒 کاربران دارای خرید: <b>{n(stats.get('buyers'))}</b> نفر\n"
        f"🎁 اکانت‌های تست: <b>{n(stats.get('trials'))}</b> نفر\n"
        f"💰 موجودی کل کاربران: <b>{n(stats.get('total_balance'))}</b> تومان\n"
        f"📦 تعداد کل فروش: <b>{n(stats.get('total_sales'))}</b> عدد\n"
        f"✅ فروش سرویس‌های فعال: <b>{n(stats.get('active_sales'))}</b> عدد\n"
        f"💵 جمع کل فروش: <b>{n(stats.get('sum_sales'))}</b> تومان\n"
        f"🟢 جمع فروش فعال: <b>{n(stats.get('sum_active'))}</b> تومان\n"
        f"🔄 جمع کل تمدید: <b>{n(stats.get('sum_renew'))}</b> تومان\n"
        f"📈 نرخ تبدیل به مشتری: <b>{stats.get('conversion', 0):.2f}٪</b>\n"
        f"📉 میانگین خرید هر مشتری: <b>{n(stats.get('avg_buy'))}</b> تومان\n"
        f"📅 درآمد پیش‌بینی‌شده ماهانه: <b>{n(stats.get('forecast_month'))}</b> تومان\n"
        f"🔁 درصد تمدید از فروش: <b>{stats.get('renew_pct', 0):.2f}٪</b>\n"
        f"🤝 تعداد کل نمایندگان: <b>{n(stats.get('resellers') + stats.get('resellers_vip', 0))}</b> نفر\n"
        f"   • نماینده عادی: <b>{n(stats.get('resellers'))}</b>\n"
        f"   • نماینده ویژه: <b>{n(stats.get('resellers_vip'))}</b>\n"
        f"🖥 تعداد پنل‌ها: <b>{n(stats.get('panels'))}</b> عدد\n"
        f"⚡ پینگ ربات: <b>{ping_ms}</b> میلی‌ثانیه\n"
        f"🏦 درگاه: <b>{stats.get('gateway') or '—'}</b>\n"
        f"   • پرداخت موفق: <b>{n(stats.get('pay_ok'))}</b>\n"
        f"   • جمع پرداختی‌ها: <b>{n(stats.get('pay_sum'))}</b> تومان"
    )
