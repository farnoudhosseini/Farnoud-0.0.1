# تیکت پشتیبانی و دپارتمان‌ها + متن آموزش

from __future__ import annotations
from typing import Optional
from database import get_sync_connection, get_setting_sync, set_setting_sync

def ensure_support_tables():
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS support_departments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(120) NOT NULL,
                description VARCHAR(255) DEFAULT NULL,
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                sort_order INT NOT NULL DEFAULT 0
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                department_id INT DEFAULT NULL,
                subject VARCHAR(200) NOT NULL,
                status ENUM('open','answered','closed') NOT NULL DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_tg (telegram_id),
                INDEX idx_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS support_messages (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                ticket_id INT NOT NULL,
                sender ENUM('user','admin') NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_ticket (ticket_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            cur.execute("SELECT COUNT(*) AS c FROM support_departments")
            if (cur.fetchone() or {}).get("c", 0) == 0:
                for i, name in enumerate(["فنی", "مالی", "فروش"], 1):
                    cur.execute(
                        "INSERT INTO support_departments (name, sort_order) VALUES (%s,%s)",
                        (name, i),
                    )
            # پیام‌های پیش‌فرض
            defaults = [
                ("btn_services", "دکمه سرویس‌ها", "📱 سرویس‌های من"),
                ("btn_support", "دکمه پشتیبانی", "🛠 پشتیبانی"),
                ("btn_education", "دکمه آموزش", "📚 آموزش"),
                ("education_text", "متن آموزش", "📚 مرکز آموزش\n\nآموزش اتصال را اینجا قرار دهید.\nاین متن از پنل مدیریت قابل تغییر است."),
                ("support_welcome", "شروع پشتیبانی", "🛠 پشتیبانی\nدپارتمان مورد نظر را انتخاب کنید:"),
            ]
            for key, title, body in defaults:
                cur.execute(
                    "INSERT IGNORE INTO message_templates (`key`, title, body) VALUES (%s,%s,%s)",
                    (key, title, body),
                )
            conn.commit()
    finally:
        conn.close()

def list_departments(active_only=True):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            if active_only:
                cur.execute("SELECT * FROM support_departments WHERE is_active=1 ORDER BY sort_order, id")
            else:
                cur.execute("SELECT * FROM support_departments ORDER BY sort_order, id")
            return cur.fetchall() or []
    finally:
        conn.close()

def add_department(name, description=None):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO support_departments (name, description) VALUES (%s,%s)", (name, description))
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()

def delete_department(did):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM support_departments WHERE id=%s", (did,))
            conn.commit()
    finally:
        conn.close()

def create_ticket(telegram_id, department_id, subject) -> int:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO support_tickets (telegram_id, department_id, subject) VALUES (%s,%s,%s)",
                (telegram_id, department_id, subject),
            )
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()

def add_ticket_message(ticket_id, sender, message):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO support_messages (ticket_id, sender, message) VALUES (%s,%s,%s)",
                (ticket_id, sender, message),
            )
            st = "answered" if sender == "admin" else "open"
            cur.execute("UPDATE support_tickets SET status=%s WHERE id=%s AND status!='closed'", (st, ticket_id))
            conn.commit()
    finally:
        conn.close()

def get_ticket(tid):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM support_tickets WHERE id=%s", (tid,))
            return cur.fetchone()
    finally:
        conn.close()

def list_user_tickets(telegram_id, limit=20):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM support_tickets WHERE telegram_id=%s ORDER BY id DESC LIMIT %s",
                (telegram_id, limit),
            )
            return cur.fetchall() or []
    finally:
        conn.close()

def list_open_tickets(limit=50):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM support_tickets WHERE status!='closed' ORDER BY updated_at DESC LIMIT %s",
                (limit,),
            )
            return cur.fetchall() or []
    finally:
        conn.close()

def get_ticket_messages(ticket_id):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM support_messages WHERE ticket_id=%s ORDER BY id ASC",
                (ticket_id,),
            )
            return cur.fetchall() or []
    finally:
        conn.close()

def close_ticket(ticket_id):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE support_tickets SET status='closed' WHERE id=%s", (ticket_id,))
            conn.commit()
    finally:
        conn.close()

def list_user_orders(telegram_id, limit=50):
    """سرویس‌های خریداری‌شده کاربر"""
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT o.*, p.name AS product_name, p.volume_gb, p.duration_days, p.price,
                          vp.name AS panel_name, vp.base_url AS panel_base, vp.username AS panel_user,
                          vp.password AS panel_pass
                   FROM service_orders o
                   LEFT JOIN products p ON p.id=o.product_id
                   LEFT JOIN vpn_panels vp ON vp.id=o.panel_id
                   WHERE o.telegram_id=%s AND o.status IN ('paid','provisioned')
                   ORDER BY o.id DESC LIMIT %s""",
                (telegram_id, limit),
            )
            return cur.fetchall() or []
    finally:
        conn.close()

def get_user_order(order_id, telegram_id=None):
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            if telegram_id:
                cur.execute(
                    """SELECT o.*, p.name AS product_name, p.volume_gb, p.duration_days,
                              vp.name AS panel_name, vp.base_url, vp.username AS panel_user, vp.password AS panel_pass
                       FROM service_orders o
                       LEFT JOIN products p ON p.id=o.product_id
                       LEFT JOIN vpn_panels vp ON vp.id=o.panel_id
                       WHERE o.id=%s AND o.telegram_id=%s""",
                    (order_id, telegram_id),
                )
            else:
                cur.execute("SELECT * FROM service_orders WHERE id=%s", (order_id,))
            return cur.fetchone()
    finally:
        conn.close()
