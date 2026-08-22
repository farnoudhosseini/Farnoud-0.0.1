# ادیت سرویس فروخته‌شده + سینک با پاسارگارد

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional

from db_products import get_order_full, update_order, get_product
from services.pasarguard import PasarGuardClient, gb_to_bytes


def _client_from_order(o: dict) -> PasarGuardClient:
    base = o.get("base_url") or ""
    user = o.get("panel_user") or o.get("username") or ""
    pwd = o.get("panel_pass") or o.get("password") or ""
    if not base or not user:
        raise RuntimeError("اطلاعات پنل ناقص است")
    return PasarGuardClient(base, user, pwd, verify_ssl=False)


def edit_sold_service(
    order_id: int,
    *,
    volume_gb: Optional[float] = None,
    duration_days: Optional[int] = None,
    expire_iso: Optional[str] = None,
    hwid_limit: Optional[int] = None,
    status: Optional[str] = None,
    note: Optional[str] = None,
) -> dict:
    """
    ویرایش سرویس فروخته‌شده و اعمال روی پاسارگارد.
    volume_gb: حجم جدید (گیگ) — None یعنی بدون تغییر
    duration_days: اگر داده شود، expire از الان + این تعداد روز محاسبه می‌شود
    expire_iso: تاریخ انقضای مستقیم ISO
    hwid_limit: None بدون تغییر، 0 یا منفی = نامحدود
    status: active | disabled | on_hold
    """
    o = get_order_full(order_id)
    if not o:
        return {"ok": False, "error": "سفارش یافت نشد"}
    if not o.get("vpn_username"):
        return {"ok": False, "error": "اکانت VPN متصل نیست"}

    payload = {}
    local_fields = {}

    if volume_gb is not None:
        try:
            vg = float(volume_gb)
        except (TypeError, ValueError):
            return {"ok": False, "error": "حجم نامعتبر"}
        if vg <= 0:
            payload["data_limit"] = 0  # unlimited
        else:
            payload["data_limit"] = gb_to_bytes(vg)
        local_fields["volume_gb_override"] = vg if vg > 0 else None

    if duration_days is not None:
        try:
            days = int(duration_days)
        except (TypeError, ValueError):
            return {"ok": False, "error": "مدت نامعتبر"}
        exp = datetime.now(timezone.utc) + timedelta(days=max(0, days))
        payload["expire"] = exp.isoformat()
        local_fields["duration_days_override"] = days
        local_fields["expire_at"] = exp.strftime("%Y-%m-%d %H:%M:%S")
    elif expire_iso:
        payload["expire"] = expire_iso
        local_fields["expire_at"] = expire_iso[:19].replace("T", " ")

    if hwid_limit is not None:
        if int(hwid_limit) <= 0:
            payload["hwid_limit"] = None
        else:
            payload["hwid_limit"] = int(hwid_limit)

    if status:
        payload["status"] = status

    if note is not None:
        local_fields["admin_note"] = note

    try:
        client = _client_from_order(o)
        if payload:
            client.modify_user(o["vpn_username"], payload)
        if local_fields:
            update_order(order_id, **local_fields)
        full = client.get_user(o["vpn_username"])
        return {"ok": True, "user": full, "order_id": order_id}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def process_hourly_charges() -> list:
    """
    کسر هزینه ساعتی از کاربران فعال.
    باید توسط job هر چند دقیقه/ساعت صدا زده شود.
    """
    from database import get_setting_sync
    from db_users import add_balance, get_bot_user
    from db_products import list_all_orders

    if get_setting_sync("hourly_global_enabled", "0") != "1":
        return []

    results = []
    # سفارش‌های ساعتی فعال
    from database import get_sync_connection
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT o.*, p.hourly_price AS product_hourly_price
                   FROM service_orders o
                   LEFT JOIN products p ON p.id=o.product_id
                   WHERE o.is_hourly=1 AND o.hourly_active=1 AND o.status='provisioned'"""
            )
            rows = cur.fetchall() or []
    finally:
        conn.close()

    now = datetime.now(timezone.utc)
    for o in rows:
        rate = o.get("hourly_rate") or o.get("product_hourly_price") or 0
        try:
            rate = float(rate)
        except Exception:
            rate = 0
        if rate <= 0:
            continue
        last = o.get("hourly_last_charge_at") or o.get("hourly_started_at")
        if last:
            if isinstance(last, str):
                try:
                    last_dt = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
                except Exception:
                    last_dt = now - timedelta(hours=1)
            else:
                last_dt = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
        else:
            last_dt = now - timedelta(hours=1)

        hours = max(0, int((now - last_dt).total_seconds() // 3600))
        if hours < 1:
            continue
        charge = int(rate * hours)
        bu = get_bot_user(o["telegram_id"])
        bal = int((bu or {}).get("balance") or 0)
        if bal < charge:
            # موجودی کافی نیست → توقف سرویس ساعتی
            try:
                client = _client_from_order(o)
                if o.get("vpn_username"):
                    client.modify_user(o["vpn_username"], {"status": "disabled"})
            except Exception as e:
                results.append({"order_id": o["id"], "error": str(e)})
            update_order(o["id"], hourly_active=0)
            results.append({
                "order_id": o["id"],
                "telegram_id": o["telegram_id"],
                "stopped": True,
                "reason": "insufficient_balance",
            })
            continue

        add_balance(o["telegram_id"], -charge, f"hourly#{o['id']}x{hours}")
        update_order(
            o["id"],
            hourly_last_charge_at=now.strftime("%Y-%m-%d %H:%M:%S"),
        )
        bu2 = get_bot_user(o["telegram_id"])
        mute = bool(o.get("hourly_notify_mute"))
        results.append({
            "order_id": o["id"],
            "telegram_id": o["telegram_id"],
            "charged": charge,
            "hours": hours,
            "balance_after": int((bu2 or {}).get("balance") or 0),
            "mute_notify": mute,
        })
    return results


def stop_hourly_service(order_id: int, telegram_id: int = None) -> dict:
    """حذف/توقف سرویس ساعتی توسط کاربر"""
    o = get_order_full(order_id)
    if not o:
        return {"ok": False, "error": "یافت نشد"}
    if telegram_id and o["telegram_id"] != telegram_id:
        return {"ok": False, "error": "دسترسی ندارید"}
    if not o.get("is_hourly"):
        return {"ok": False, "error": "این سرویس ساعتی نیست"}
    try:
        if o.get("vpn_username"):
            client = _client_from_order(o)
            client.modify_user(o["vpn_username"], {"status": "disabled"})
        update_order(order_id, hourly_active=0, status="cancelled")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
