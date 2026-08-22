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
