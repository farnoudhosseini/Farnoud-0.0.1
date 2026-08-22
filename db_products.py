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
            cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                category_id INT DEFAULT NULL,
                price DECIMAL(18,0) NOT NULL DEFAULT 0,
                volume_gb DECIMAL(12,2) NOT NULL DEFAULT 0,
                duration_days INT NOT NULL DEFAULT 30,
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
            cur.execute("""
            CREATE TABLE IF NOT EXISTS product_panels (
                product_id INT NOT NULL,
                panel_id INT NOT NULL,
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
            # پیام‌های خرید
            msgs = [
                ("btn_buy", "دکمه خرید", "🛒 خرید سرویس جدید"),
                ("btn_wallet", "دکمه کیف پول", "💰 کیف پول من"),
                ("buy_select_panel", "انتخاب پنل", "🖥 پنل مورد نظر را انتخاب کنید:"),
                ("buy_select_category", "انتخاب دسته", "📁 دسته‌بندی را انتخاب کنید:"),
                ("buy_select_product", "انتخاب محصول", "📦 محصول را انتخاب کنید:"),
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
    allowed = {"name", "sort_order", "is_active"}
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
            cur.execute("SELECT panel_id FROM product_panels WHERE product_id=%s", (pid,))
            r["panel_ids"] = [x["panel_id"] for x in (cur.fetchall() or [])]
            cur.execute(
                """SELECT vp.id, vp.name FROM product_panels pp
                   JOIN vpn_panels vp ON vp.id=pp.panel_id WHERE pp.product_id=%s""",
                (pid,),
            )
            r["panels"] = cur.fetchall() or []
            return r
    finally:
        conn.close()

def create_product(name, price, volume_gb, duration_days, target_role="all",
                   category_id=None, description=None, panel_ids=None) -> int:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(sort_order),0)+1 AS n FROM products")
            n = (cur.fetchone() or {}).get("n") or 1
            cur.execute(
                """INSERT INTO products (name, category_id, price, volume_gb, duration_days, target_role, description, sort_order)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (name, category_id, price, volume_gb, duration_days, target_role, description, n),
            )
            pid = cur.lastrowid
            for panel_id in (panel_ids or []):
                cur.execute(
                    "INSERT IGNORE INTO product_panels (product_id, panel_id) VALUES (%s,%s)",
                    (pid, int(panel_id)),
                )
            conn.commit()
            return pid
    finally:
        conn.close()

def update_product(pid: int, panel_ids=None, **fields):
    allowed = {"name", "category_id", "price", "volume_gb", "duration_days",
               "target_role", "description", "sort_order", "is_active"}
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"`{k}`=%s"); vals.append(v)
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            if sets:
                vals.append(pid)
                cur.execute(f"UPDATE products SET {','.join(sets)} WHERE id=%s", vals)
            if panel_ids is not None:
                cur.execute("DELETE FROM product_panels WHERE product_id=%s", (pid,))
                for panel_id in panel_ids:
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
               "wallet_used", "pay_amount"}
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
