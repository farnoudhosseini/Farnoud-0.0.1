# محصولات، دسته‌بندی و سفارش سرویس

from __future__ import annotations
from typing import Optional
from database import get_sync_connection

ROLE_OPTIONS = {
    "user": "کاربر عادی",
    "vip": "کاربر VIP",
    "reseller": "نماینده عادی",
    "reseller_vip": "نماینده ویژه",
    "all": "همه نقش‌ها",
}

def ensure_product_tables():
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS product_categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(120) NOT NULL,
                sort_order INT NOT NULL DEFAULT 0,
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            for col, ddl in [
                ("emoji", "VARCHAR(32) DEFAULT NULL"),
                ("premium_emoji", "VARCHAR(64) DEFAULT NULL"),
            ]:
                try:
                    cur.execute(f"ALTER TABLE product_categories ADD COLUMN {col} {ddl}")
                except Exception:
                    pass
            cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                category_id INT DEFAULT NULL,
                price DECIMAL(18,0) NOT NULL DEFAULT 0,
                volume_gb DECIMAL(12,2) NOT NULL DEFAULT 0,
                duration_days INT NOT NULL DEFAULT 30,
                hwid_limit INT DEFAULT NULL,
                target_role VARCHAR(30) NOT NULL DEFAULT 'all',
                description TEXT,
                sort_order INT NOT NULL DEFAULT 0,
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_cat (category_id),
                INDEX idx_sort (sort_order)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            # مهاجرت: اضافه کردن hwid_limit اگر ستون وجود نداشته باشد
            try:
                cur.execute("ALTER TABLE products ADD COLUMN hwid_limit INT DEFAULT NULL AFTER duration_days")
            except Exception:
                pass  # ستون از قبل وجود دارد
            # 3x-ui 3.7.0 lifecycle fields (optional, NULL = default behaviour)
            for col, ddl in (
                ("limit_hwid", "INT DEFAULT NULL"),
                ("reset_day", "INT DEFAULT NULL"),
                ("reset_max", "INT DEFAULT NULL"),
                ("traffic_reset", "VARCHAR(20) DEFAULT NULL"),
                ("traffic_reset_day", "INT DEFAULT NULL"),
            ):
                try:
                    cur.execute(f"ALTER TABLE products ADD COLUMN {col} {ddl}")
                except Exception:
                    pass
            cur.execute("""
            CREATE TABLE IF NOT EXISTS product_panels (
                product_id INT NOT NULL,
                panel_id INT NOT NULL,
                extra_json TEXT NULL,
                PRIMARY KEY (product_id, panel_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS service_orders (
                id INT AUTO_INCREMENT PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                product_id INT NOT NULL,
                panel_id INT NOT NULL,
                amount DECIMAL(18,0) NOT NULL,
                wallet_used DECIMAL(18,0) NOT NULL DEFAULT 0,
                pay_amount DECIMAL(18,0) NOT NULL DEFAULT 0,
                status ENUM('pending_payment','waiting_receipt','pending_review','paid','provisioned','cancelled','rejected') NOT NULL DEFAULT 'pending_payment',
                method_key VARCHAR(40) DEFAULT NULL,
                card_id INT DEFAULT NULL,
                receipt_file_id VARCHAR(255) DEFAULT NULL,
                vpn_username VARCHAR(100) DEFAULT NULL,
                admin_note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_tg (telegram_id),
                INDEX idx_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            # Safe Variza migration for existing service orders.
            for col, ddl in [("variza_slug", "VARCHAR(120) DEFAULT NULL"),("variza_amount", "DECIMAL(18,0) DEFAULT NULL"),("variza_attempt_code", "VARCHAR(120) DEFAULT NULL"),("variza_delivery_id", "VARCHAR(120) DEFAULT NULL"),("paid_at", "TIMESTAMP NULL")]:
                try: cur.execute(f"ALTER TABLE service_orders ADD COLUMN {col} {ddl}")
                except Exception: pass
            try: cur.execute("CREATE UNIQUE INDEX uniq_order_variza_slug ON service_orders (variza_slug)")
            except Exception: pass

            # پیام‌های خرید
            msgs = [
                ("btn_buy", "دکمه خرید", "🛒 خرید سرویس جدید"),
                ("btn_wallet", "دکمه کیف پول", "💰 کیف پول من"),
                ("buy_select_panel", "انتخاب پنل", "🖥 پنل مورد نظر را انتخاب کنید:"),
                ("buy_select_category", "انتخاب دسته", "📁 دسته‌بندی را انتخاب کنید:"),
                ("buy_select_product", "انتخاب محصول", "📦 محصول را انتخاب کنید:"),
                ("service_delivered", "تحویل سرویس", "📦 سرویس [service_volume] گیگابایت - [service_expiration] روز\n📊 وضعیت: [status]\n📱 تعداد دستگاه‌های متصل به این سرویس: [hwid_s]\n🔢 شماره سرویس: [service_id]\n⏳ زمان باقی‌مانده: [service_expiration] روز\n💾 حجم باقی‌مانده: [service_volume] گیگابایت\n🔗 لینک اتصال:\n[subscription_link]\nℹ️ توجه: آموزش اتصال به سرویس‌ها را می‌توانید در بخش «مرکز آموزش» ببینید.\n🔐 برای تغییر رمز و قطع دسترسی افراد متصل به پروکسی روی دکمه زیر کلیک کنید\n[channel_id]"),
                ("buy_invoice", "فاکتور خرید", "🧾 فاکتور خرید\n\nمحصول: [product_name]\nپنل: [panel_name]\nقیمت: [price] تومان\nموجودی کیف پول: [balance] تومان\nمبلغ قابل پرداخت: [pay_amount] تومان\n\n[description]"),
            ]
            for key, title, body in msgs:
                cur.execute(
                    """INSERT IGNORE INTO message_templates (`key`, title, body) VALUES (%s,%s,%s)""",
                    (key, title, body),
                )
            conn.commit()
    finally:
        conn.close()

# ---- categories ----
def list_categories(active_only=False):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            if active_only:
                cur.execute("SELECT * FROM product_categories WHERE is_active=1 ORDER BY sort_order, id")
            else:
                cur.execute("SELECT * FROM product_categories ORDER BY sort_order, id")
            return cur.fetchall() or []
    finally:
        conn.close()

def add_category(name: str) -> int:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(sort_order),0)+1 AS n FROM product_categories")
            n = (cur.fetchone() or {}).get("n") or 1
            cur.execute("INSERT INTO product_categories (name, sort_order) VALUES (%s,%s)", (name, n))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()

def update_category(cid: int, **fields):
    allowed = {"name", "sort_order", "is_active", "emoji", "premium_emoji"}
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"`{k}`=%s"); vals.append(v)
    if not sets:
        return
    vals.append(cid)
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE product_categories SET {','.join(sets)} WHERE id=%s", vals)
            conn.commit()
    finally:
        conn.close()

def delete_category(cid: int):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE products SET category_id=NULL WHERE category_id=%s", (cid,))
            cur.execute("DELETE FROM product_categories WHERE id=%s", (cid,))
            conn.commit()
    finally:
        conn.close()

# ---- products ----
def list_products(category_id=None, panel_id=None, role=None, active_only=False):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            sql = """SELECT p.*, c.name AS category_name
                     FROM products p
                     LEFT JOIN product_categories c ON c.id = p.category_id
                     WHERE 1=1"""
            params = []
            if active_only:
                sql += " AND p.is_active=1"
            if category_id:
                sql += " AND p.category_id=%s"; params.append(category_id)
            if role and role != "all":
                sql += " AND (p.target_role='all' OR p.target_role=%s)"; params.append(role)
            sql += " ORDER BY p.sort_order, p.id"
            cur.execute(sql, params)
            rows = cur.fetchall() or []
            if panel_id:
                filtered = []
                for r in rows:
                    cur.execute("SELECT 1 FROM product_panels WHERE product_id=%s AND panel_id=%s", (r["id"], panel_id))
                    if cur.fetchone():
                        filtered.append(r)
                rows = filtered
            for r in rows:
                cur.execute(
                    """SELECT vp.id, vp.name FROM product_panels pp
                       JOIN vpn_panels vp ON vp.id=pp.panel_id WHERE pp.product_id=%s""",
                    (r["id"],),
                )
                r["panels"] = cur.fetchall() or []
            return rows
    finally:
        conn.close()

def get_product(pid: int) -> Optional[dict]:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT p.*, c.name AS category_name FROM products p
                   LEFT JOIN product_categories c ON c.id=p.category_id WHERE p.id=%s""",
                (pid,),
            )
            r = cur.fetchone()
            if not r:
                return None
            cur.execute("SELECT panel_id, extra_json FROM product_panels WHERE product_id=%s", (pid,))
            rows = cur.fetchall() or []
            r["panel_ids"] = [x["panel_id"] for x in rows]
            import json as _json
            r["panel_config"] = {}
            for x in rows:
                cfg = {}
                if x.get("extra_json"):
                    try:
                        cfg = _json.loads(x["extra_json"]) or {}
                    except Exception:
                        cfg = {}
                r["panel_config"][int(x["panel_id"])] = cfg
            cur.execute(
                """SELECT vp.id, vp.name, vp.panel_type, pp.extra_json FROM product_panels pp
                   JOIN vpn_panels vp ON vp.id=pp.panel_id WHERE pp.product_id=%s""",
                (pid,),
            )
            r["panels"] = cur.fetchall() or []
            return r
    finally:
        conn.close()

def create_product(name, price, volume_gb, duration_days, target_role="all",
                   category_id=None, description=None, panel_ids=None, hwid_limit=None,
                   panel_config=None, limit_hwid=None, reset_day=None, reset_max=None,
                   traffic_reset=None, traffic_reset_day=None) -> int:
    """panel_config: {panel_id: {"group_ids": [...]} or {"inbound_ids": [...]}}"""
    ensure_product_panel_extra()
    import json as _json
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(sort_order),0)+1 AS n FROM products")
            n = (cur.fetchone() or {}).get("n") or 1
            cur.execute(
                """INSERT INTO products (name, category_id, price, volume_gb, duration_days, hwid_limit,
                   target_role, description, sort_order, limit_hwid, reset_day, reset_max, traffic_reset, traffic_reset_day)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (name, category_id, price, volume_gb, duration_days, hwid_limit, target_role, description, n,
                 limit_hwid, reset_day, reset_max, traffic_reset, traffic_reset_day),
            )
            pid = cur.lastrowid
            panel_config = panel_config or {}
            for panel_id in (panel_ids or []):
                cfg = panel_config.get(int(panel_id)) or panel_config.get(str(panel_id)) or {}
                extra = _json.dumps(cfg, ensure_ascii=False) if cfg else None
                try:
                    cur.execute(
                        "INSERT INTO product_panels (product_id, panel_id, extra_json) VALUES (%s,%s,%s)",
                        (pid, int(panel_id), extra),
                    )
                except Exception:
                    cur.execute(
                        "INSERT IGNORE INTO product_panels (product_id, panel_id) VALUES (%s,%s)",
                        (pid, int(panel_id)),
                    )
            conn.commit()
            return pid
    finally:
        conn.close()

def update_product(pid: int, panel_ids=None, panel_config=None, **fields):
    allowed = {"name", "category_id", "price", "volume_gb", "duration_days", "hwid_limit",
               "target_role", "description", "sort_order", "is_active", "hourly_enabled", "hourly_price",
               "limit_hwid", "reset_day", "reset_max", "traffic_reset", "traffic_reset_day", "start_on_first_connect"}
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"`{k}`=%s"); vals.append(v)
    ensure_product_panel_extra()
    import json as _json
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            if sets:
                vals.append(pid)
                cur.execute(f"UPDATE products SET {','.join(sets)} WHERE id=%s", vals)
            if panel_ids is not None:
                cur.execute("DELETE FROM product_panels WHERE product_id=%s", (pid,))
                panel_config = panel_config or {}
                for panel_id in panel_ids:
                    cfg = panel_config.get(int(panel_id)) or panel_config.get(str(panel_id)) or {}
                    extra = _json.dumps(cfg, ensure_ascii=False) if cfg else None
                    try:
                        cur.execute(
                            "INSERT INTO product_panels (product_id, panel_id, extra_json) VALUES (%s,%s,%s)",
                            (pid, int(panel_id), extra),
                        )
                    except Exception:
                        cur.execute(
                            "INSERT INTO product_panels (product_id, panel_id) VALUES (%s,%s)",
                            (pid, int(panel_id)),
                        )
            conn.commit()
    finally:
        conn.close()

def delete_product(pid: int):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM product_panels WHERE product_id=%s", (pid,))
            cur.execute("DELETE FROM products WHERE id=%s", (pid,))
            conn.commit()
    finally:
        conn.close()

def move_product(pid: int, direction: str):
    """direction: up | down"""
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, sort_order FROM products WHERE id=%s", (pid,))
            cur_p = cur.fetchone()
            if not cur_p:
                return
            if direction == "up":
                cur.execute(
                    "SELECT id, sort_order FROM products WHERE sort_order < %s ORDER BY sort_order DESC LIMIT 1",
                    (cur_p["sort_order"],),
                )
            else:
                cur.execute(
                    "SELECT id, sort_order FROM products WHERE sort_order > %s ORDER BY sort_order ASC LIMIT 1",
                    (cur_p["sort_order"],),
                )
            other = cur.fetchone()
            if other:
                cur.execute("UPDATE products SET sort_order=%s WHERE id=%s", (other["sort_order"], cur_p["id"]))
                cur.execute("UPDATE products SET sort_order=%s WHERE id=%s", (cur_p["sort_order"], other["id"]))
                conn.commit()
    finally:
        conn.close()

# ---- orders ----
def create_order(telegram_id, product_id, panel_id, amount, wallet_used, pay_amount) -> int:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            status = "paid" if pay_amount <= 0 else "pending_payment"
            cur.execute(
                """INSERT INTO service_orders
                   (telegram_id, product_id, panel_id, amount, wallet_used, pay_amount, status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (telegram_id, product_id, panel_id, amount, wallet_used, pay_amount, status),
            )
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()

def get_order(oid: int):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM service_orders WHERE id=%s", (oid,))
            return cur.fetchone()
    finally:
        conn.close()

def update_order(oid: int, **fields):
    allowed = {"status", "method_key", "card_id", "receipt_file_id", "vpn_username", "admin_note",
               "wallet_used", "pay_amount", "custom_name", "is_hourly", "hourly_rate", "hourly_active",
               "volume_gb_override", "duration_days_override", "expire_at", "panel_id", "product_id",
               "variza_slug", "variza_amount", "variza_attempt_code", "variza_delivery_id", "paid_at",
               "protocol_override", "inbound_id"}
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"`{k}`=%s"); vals.append(v)
    if not sets:
        return
    vals.append(oid)
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE service_orders SET {','.join(sets)} WHERE id=%s", vals)
            conn.commit()
    finally:
        conn.close()


# ---- مدیریت سرویس‌های فروخته‌شده + ساعتی ----

def ensure_service_mgmt_columns():
    """ستون‌های اضافه برای ساعتی و ادیت سرویس"""
    # pricing features bootstrapped lazily via ensure_pricing_features
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            for col, ddl in [
                ("is_hourly", "TINYINT(1) NOT NULL DEFAULT 0"),
                ("hourly_rate", "DECIMAL(18,2) DEFAULT NULL"),
                ("hourly_active", "TINYINT(1) NOT NULL DEFAULT 0"),
                ("hourly_started_at", "TIMESTAMP NULL DEFAULT NULL"),
                ("hourly_last_charge_at", "TIMESTAMP NULL DEFAULT NULL"),
                ("volume_gb_override", "DECIMAL(12,2) DEFAULT NULL"),
                ("duration_days_override", "INT DEFAULT NULL"),
                ("expire_at", "TIMESTAMP NULL DEFAULT NULL"),
                ("custom_name", "VARCHAR(100) DEFAULT NULL"),
                ("hourly_notify_mute", "TINYINT(1) NOT NULL DEFAULT 0"),
                ("inbound_id", "INT DEFAULT NULL"),
                ("protocol_override", "TEXT DEFAULT NULL"),
            ]:
                try:
                    cur.execute(f"ALTER TABLE service_orders ADD COLUMN {col} {ddl}")
                except Exception:
                    pass
            # محصولات: پشتیبانی ساعتی
            for col, ddl in [
                ("hourly_enabled", "TINYINT(1) NOT NULL DEFAULT 0"),
                ("hourly_price", "DECIMAL(18,2) DEFAULT NULL"),
            ]:
                try:
                    cur.execute(f"ALTER TABLE products ADD COLUMN {col} {ddl}")
                except Exception:
                    pass
            # تنظیمات سراسری ساعتی
            for k, v in [
                ("hourly_global_enabled", "0"),
                ("inline_main_menu", "0"),
                ("report_group_id", ""),
                ("report_topic_sales", ""),
                ("report_topic_charges", ""),
                ("report_topic_tickets", ""),
                ("report_topic_errors", ""),
                ("report_topic_backup", ""),
            ]:
                cur.execute("INSERT IGNORE INTO settings (`key`, `value`) VALUES (%s,%s)", (k, v))
            conn.commit()
    finally:
        conn.close()


def list_all_orders(status=None, limit=100, offset=0, search=None):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            sql = """SELECT o.*, p.name AS product_name, p.volume_gb, p.duration_days,
                            vp.name AS panel_name, u.username, u.first_name
                     FROM service_orders o
                     LEFT JOIN products p ON p.id=o.product_id
                     LEFT JOIN vpn_panels vp ON vp.id=o.panel_id
                     LEFT JOIN bot_users u ON u.telegram_id=o.telegram_id
                     WHERE 1=1"""
            vals = []
            if status:
                sql += " AND o.status=%s"
                vals.append(status)
            if search:
                sql += " AND (o.vpn_username LIKE %s OR CAST(o.telegram_id AS CHAR) LIKE %s OR CAST(o.id AS CHAR)=%s)"
                q = f"%{search}%"
                vals.extend([q, q, search])
            sql += " ORDER BY o.id DESC LIMIT %s OFFSET %s"
            vals.extend([limit, offset])
            cur.execute(sql, vals)
            return cur.fetchall() or []
    finally:
        conn.close()


def get_order_full(oid: int):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT o.*, p.name AS product_name, p.volume_gb, p.duration_days, p.hwid_limit,
                          p.hourly_enabled AS product_hourly, p.hourly_price AS product_hourly_price,
                          vp.name AS panel_name, vp.base_url, vp.username AS panel_user, vp.password AS panel_pass,
                          vp.panel_type, vp.api_key
                   FROM service_orders o
                   LEFT JOIN products p ON p.id=o.product_id
                   LEFT JOIN vpn_panels vp ON vp.id=o.panel_id
                   WHERE o.id=%s""",
                (oid,),
            )
            return cur.fetchone()
    finally:
        conn.close()


# گسترش update_order برای فیلدهای جدید
_ORIG_UPDATE_ORDER = update_order

def update_order(oid: int, **fields):
    allowed = {
        "status", "method_key", "card_id", "receipt_file_id", "vpn_username", "admin_note",
        "wallet_used", "pay_amount", "amount", "is_hourly", "hourly_rate", "hourly_active",
        "hourly_started_at", "hourly_last_charge_at", "volume_gb_override",
        "duration_days_override", "expire_at", "custom_name", "panel_id", "product_id",
        "hourly_notify_mute", "inbound_id", "coupon_code", "discount_amount",
    }
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"`{k}`=%s")
            vals.append(v)
    if not sets:
        return
    vals.append(oid)
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE service_orders SET {','.join(sets)} WHERE id=%s", vals)
            conn.commit()
    finally:
        conn.close()


def reorder_products(ids: list) -> bool:
    """Persist drag/drop product order. IDs are applied atomically in the supplied order."""
    ids = [int(x) for x in ids if str(x).isdigit()]
    if not ids:
        return False
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            for pos, pid in enumerate(ids):
                cur.execute("UPDATE products SET sort_order=%s WHERE id=%s", (pos, pid))
            conn.commit()
        return True
    finally:
        conn.close()

def ensure_product_panel_extra():
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("ALTER TABLE product_panels ADD COLUMN extra_json TEXT NULL")
            except Exception:
                pass
            conn.commit()
    finally:
        conn.close()


# ============== قیمت اختصاصی پنل / زمان‌بندی قیمت / عملیات گروهی / اولین اتصال ==============

def ensure_pricing_features():
    """جداول و ستون‌های قیمت پنل، زمان‌بندی قیمت، on_hold"""
    ensure_service_mgmt_columns()
    ensure_product_panel_extra()
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            for col, ddl in [
                ("start_on_first_connect", "TINYINT(1) NOT NULL DEFAULT 0"),
            ]:
                try:
                    cur.execute(f"ALTER TABLE products ADD COLUMN {col} {ddl}")
                except Exception:
                    pass
            cur.execute("""
            CREATE TABLE IF NOT EXISTS price_schedules (
                id INT AUTO_INCREMENT PRIMARY KEY,
                product_id INT NOT NULL,
                panel_id INT DEFAULT NULL,
                change_type ENUM('fixed','percent') NOT NULL DEFAULT 'percent',
                price_mode ENUM('fixed_price','hourly_price','both') NOT NULL DEFAULT 'fixed_price',
                value DECIMAL(18,4) NOT NULL,
                direction ENUM('increase','decrease') NOT NULL DEFAULT 'increase',
                run_at DATETIME NOT NULL,
                status ENUM('pending','done','cancelled') NOT NULL DEFAULT 'pending',
                note VARCHAR(255) DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                applied_at TIMESTAMP NULL DEFAULT NULL,
                INDEX idx_run (status, run_at),
                INDEX idx_prod (product_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            conn.commit()
    finally:
        conn.close()


def get_panel_price(product: dict, panel_id: int, hourly: bool = False) -> int:
    """
    قیمت مؤثر محصول برای یک پنل.
    اگر در extra_json پنل قیمت ست شده باشد همان؛ وگرنه قیمت اصلی محصول.
    """
    ensure_pricing_features()
    pid = int(panel_id)
    cfg = {}
    try:
        cfg = (product.get("panel_config") or {}).get(pid) or (product.get("panel_config") or {}).get(str(pid)) or {}
    except Exception:
        cfg = {}
    if hourly:
        if cfg.get("hourly_price") is not None and str(cfg.get("hourly_price")).strip() != "":
            try:
                return int(float(cfg["hourly_price"]))
            except (TypeError, ValueError):
                pass
        return int(float(product.get("hourly_price") or 0))
    if cfg.get("price") is not None and str(cfg.get("price")).strip() != "":
        try:
            return int(float(cfg["price"]))
        except (TypeError, ValueError):
            pass
    return int(float(product.get("price") or 0))


def _apply_delta(current, direction: str, change_type: str, value) -> float:
    cur = float(current or 0)
    val = float(value or 0)
    if change_type == "percent":
        delta = cur * (val / 100.0)
    else:
        delta = val
    if direction == "decrease":
        return max(0.0, cur - delta)
    return max(0.0, cur + delta)


def list_price_schedules(status=None, limit=100):
    ensure_pricing_features()
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            if status:
                cur.execute(
                    """SELECT s.*, p.name AS product_name FROM price_schedules s
                       LEFT JOIN products p ON p.id=s.product_id
                       WHERE s.status=%s ORDER BY s.run_at ASC LIMIT %s""",
                    (status, int(limit)),
                )
            else:
                cur.execute(
                    """SELECT s.*, p.name AS product_name FROM price_schedules s
                       LEFT JOIN products p ON p.id=s.product_id
                       ORDER BY s.run_at DESC LIMIT %s""",
                    (int(limit),),
                )
            return cur.fetchall() or []
    finally:
        conn.close()


def create_price_schedule(product_id, run_at, value, direction="increase",
                          change_type="percent", price_mode="fixed_price",
                          panel_id=None, note=None) -> int:
    ensure_pricing_features()
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO price_schedules
                   (product_id, panel_id, change_type, price_mode, value, direction, run_at, note)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (int(product_id), int(panel_id) if panel_id else None,
                 change_type, price_mode, float(value), direction, run_at, note),
            )
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()


def cancel_price_schedule(sid: int):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE price_schedules SET status='cancelled' WHERE id=%s AND status='pending'", (int(sid),))
            conn.commit()
    finally:
        conn.close()


def apply_due_price_schedules() -> dict:
    """اعمال زمان‌بندی‌های سررسید — برای cron"""
    ensure_pricing_features()
    import json as _json
    stats = {"applied": 0, "errors": []}
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT * FROM price_schedules
                   WHERE status='pending' AND run_at <= NOW()
                   ORDER BY run_at ASC LIMIT 50"""
            )
            rows = cur.fetchall() or []
        for s in rows:
            try:
                prod = get_product(int(s["product_id"]))
                if not prod:
                    raise RuntimeError("product missing")
                modes = []
                pm = s.get("price_mode") or "fixed_price"
                if pm in ("fixed_price", "both"):
                    modes.append("fixed")
                if pm in ("hourly_price", "both"):
                    modes.append("hourly")
                panel_id = s.get("panel_id")
                if panel_id:
                    # قیمت فقط روی extra_json همان پنل
                    cfg = dict((prod.get("panel_config") or {}).get(int(panel_id))
                               or (prod.get("panel_config") or {}).get(str(panel_id)) or {})
                    if "fixed" in modes:
                        base = cfg.get("price")
                        if base is None or str(base).strip() == "":
                            base = prod.get("price") or 0
                        cfg["price"] = int(_apply_delta(base, s["direction"], s["change_type"], s["value"]))
                    if "hourly" in modes:
                        base = cfg.get("hourly_price")
                        if base is None or str(base).strip() == "":
                            base = prod.get("hourly_price") or 0
                        cfg["hourly_price"] = float(_apply_delta(base, s["direction"], s["change_type"], s["value"]))
                    # ذخیره
                    conn2 = get_sync_connection()
                    try:
                        with conn2.cursor() as cur2:
                            cur2.execute(
                                "UPDATE product_panels SET extra_json=%s WHERE product_id=%s AND panel_id=%s",
                                (_json.dumps(cfg, ensure_ascii=False), int(s["product_id"]), int(panel_id)),
                            )
                            conn2.commit()
                    finally:
                        conn2.close()
                else:
                    fields = {}
                    if "fixed" in modes:
                        fields["price"] = int(_apply_delta(prod.get("price") or 0, s["direction"], s["change_type"], s["value"]))
                    if "hourly" in modes:
                        fields["hourly_price"] = float(_apply_delta(prod.get("hourly_price") or 0, s["direction"], s["change_type"], s["value"]))
                    if fields:
                        update_product(int(s["product_id"]), **fields)
                conn3 = get_sync_connection()
                try:
                    with conn3.cursor() as cur3:
                        cur3.execute(
                            "UPDATE price_schedules SET status='done', applied_at=NOW() WHERE id=%s",
                            (int(s["id"]),),
                        )
                        conn3.commit()
                finally:
                    conn3.close()
                stats["applied"] += 1
            except Exception as e:
                stats["errors"].append(f"#{s.get('id')}: {e}")
    finally:
        conn.close()
    return stats


def bulk_update_products(product_ids, *, price_delta=None, price_percent=None,
                         duration_delta=None, volume_delta=None, volume_percent=None) -> int:
    """تغییر گروهی روی محصولات. delta مثبت=افزایش، منفی=کاهش. percent جداگانه."""
    ensure_pricing_features()
    ids = [int(x) for x in (product_ids or []) if str(x).isdigit()]
    if not ids:
        return 0
    n = 0
    for pid in ids:
        p = get_product(pid)
        if not p:
            continue
        fields = {}
        if price_percent is not None:
            fields["price"] = int(_apply_delta(p.get("price") or 0, "increase" if float(price_percent) >= 0 else "decrease",
                                               "percent", abs(float(price_percent))))
        elif price_delta is not None:
            fields["price"] = max(0, int(float(p.get("price") or 0) + float(price_delta)))
        if duration_delta is not None:
            fields["duration_days"] = max(0, int(float(p.get("duration_days") or 0) + float(duration_delta)))
        if volume_percent is not None:
            fields["volume_gb"] = round(_apply_delta(p.get("volume_gb") or 0, "increase" if float(volume_percent) >= 0 else "decrease",
                                                     "percent", abs(float(volume_percent))), 2)
        elif volume_delta is not None:
            fields["volume_gb"] = max(0.0, float(p.get("volume_gb") or 0) + float(volume_delta))
        if fields:
            update_product(pid, **fields)
            n += 1
    return n


def bulk_update_orders(order_ids, *, volume_delta=None, volume_percent=None,
                       duration_delta=None, extend_days=None, apply_panel: bool = True) -> dict:
    """
    تغییر گروهی سفارشات + اعمال روی پنل VPN.
    فقط در صورت موفقیت روی پنل، دیتابیس هم آپدیت می‌شود.
    برمی‌گرداند: {ok, failed, skipped, errors}
    """
    from datetime import datetime, timedelta, timezone
    ensure_pricing_features()
    ids = [int(x) for x in (order_ids or []) if str(x).isdigit()]
    stats = {"ok": 0, "failed": 0, "skipped": 0, "errors": []}

    try:
        from services.service_edit import edit_sold_service
    except Exception as e:
        return {"ok": 0, "failed": 0, "skipped": 0, "errors": [f"import edit_sold_service: {e}"]}

    for oid in ids:
        o = get_order(oid)
        if not o:
            stats["skipped"] += 1
            continue

        base_vol = o.get("volume_gb_override")
        if base_vol is None:
            try:
                pr = get_product(int(o["product_id"]))
                base_vol = pr.get("volume_gb") if pr else 0
            except Exception:
                base_vol = 0
        base_days = o.get("duration_days_override")
        if base_days is None:
            try:
                pr = get_product(int(o["product_id"]))
                base_days = pr.get("duration_days") if pr else 0
            except Exception:
                base_days = 0

        new_vol = None
        if volume_percent is not None:
            new_vol = round(_apply_delta(
                base_vol or 0,
                "increase" if float(volume_percent) >= 0 else "decrease",
                "percent",
                abs(float(volume_percent)),
            ), 2)
        elif volume_delta is not None:
            new_vol = max(0.0, float(base_vol or 0) + float(volume_delta))

        new_days = None
        expire_iso = None
        if duration_delta is not None:
            new_days = max(0, int(float(base_days or 0) + float(duration_delta)))
        if extend_days is not None:
            days_add = int(extend_days)
            exp = o.get("expire_at")
            exp_dt = None
            if exp:
                try:
                    if isinstance(exp, str):
                        exp_dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00").split(".")[0])
                    else:
                        exp_dt = exp
                except Exception:
                    exp_dt = None
            if exp_dt is None:
                base = int(base_days or 0)
                exp_dt = datetime.now(timezone.utc) + timedelta(days=max(0, base + days_add))
            else:
                if getattr(exp_dt, "tzinfo", None) is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                exp_dt = exp_dt + timedelta(days=days_add)
            expire_iso = exp_dt.astimezone(timezone.utc).isoformat()

        if new_vol is None and new_days is None and expire_iso is None:
            stats["skipped"] += 1
            continue

        # بدون اکانت VPN روی پنل قابل اعمال نیست → ناموفق، بدون تغییر DB
        if apply_panel:
            if not o.get("vpn_username") or o.get("status") not in ("paid", "provisioned"):
                stats["failed"] += 1
                stats["errors"].append(f"#{oid}: اکانت VPN/وضعیت نامعتبر — دیتابیس تغییر نکرد")
                continue
            try:
                res = edit_sold_service(
                    oid,
                    volume_gb=new_vol,
                    duration_days=new_days if expire_iso is None else None,
                    expire_iso=expire_iso,
                )
                if res.get("ok"):
                    stats["ok"] += 1
                else:
                    # هیچ تغییر DB — edit_sold_service هم فقط بعد از موفقیت پنل DB را می‌نویسد
                    stats["failed"] += 1
                    stats["errors"].append(f"#{oid}: {res.get('error') or 'اعمال روی پنل ناموفق'}")
            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(f"#{oid}: {e}")
        else:
            # حالت نادر: فقط DB (اگر صریحاً apply_panel=False)
            fields = {}
            if new_vol is not None:
                fields["volume_gb_override"] = new_vol
            if new_days is not None:
                fields["duration_days_override"] = new_days
            if expire_iso:
                fields["expire_at"] = expire_iso[:19].replace("T", " ")
            if fields:
                update_order(oid, **fields)
                stats["ok"] += 1
            else:
                stats["skipped"] += 1
    return stats

