"""Variza payment integration.

Server-side only: creates payment links and validates signed webhooks.
Variza may change the exact transfer amount shown to the payer, so webhook
matching is done by the unique payment slug, never by amount alone.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any, Optional
from urllib.parse import urlencode

import requests

from database import get_setting_sync, get_sync_connection

VARIZA_API_BASE = "https://variza.ir/api/v1"


def is_enabled() -> bool:
    return get_setting_sync("variza_enabled", "0") == "1"


def get_config() -> dict:
    return {
        "enabled": is_enabled(),
        "api_key": (get_setting_sync("variza_api_key", "") or "").strip(),
        "webhook_secret": (get_setting_sync("variza_webhook_secret", "") or "").strip(),
        "public_base_url": (get_setting_sync("public_base_url", "") or os.getenv("PUBLIC_BASE_URL", "") or "").strip().rstrip("/"),
        "title": (get_setting_sync("variza_title", "پرداخت واریزا") or "پرداخت واریزا").strip(),
    }


def callback_url() -> str:
    base = get_config()["public_base_url"]
    return f"{base}/webhooks/variza" if base else ""


def return_url(kind: str, item_id: int) -> str:
    base = get_config()["public_base_url"]
    if not base:
        return ""
    return f"{base}/payments/variza/return?{urlencode({'type': kind, 'id': item_id})}"


def configured() -> bool:
    cfg = get_config()
    return bool(cfg["api_key"] and cfg["webhook_secret"] and cfg["public_base_url"])


def create_payment_link(amount: int, kind: str, item_id: int, title: Optional[str] = None) -> dict:
    cfg = get_config()
    if not is_enabled():
        raise RuntimeError("پرداخت واریزا خاموش است")
    if not cfg["api_key"]:
        raise RuntimeError("API Key واریزا تنظیم نشده است")
    ret = return_url(kind, item_id)
    if not ret:
        raise RuntimeError("آدرس عمومی سرور (PUBLIC_BASE_URL) تنظیم نشده است")

    payload = {
        "amount": int(amount),
        "return_url": ret,
        "title": (title or cfg["title"])[:200],
        "expires_in": "1h",
    }
    r = requests.post(
        f"{VARIZA_API_BASE}/pay",
        headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text[:1000]}
    if r.status_code != 201:
        msg = data.get("message") or data.get("error") or f"HTTP {r.status_code}"
        raise RuntimeError(f"خطا در ساخت لینک واریزا: {msg}")
    if not data.get("slug") or not data.get("pay_url"):
        raise RuntimeError("پاسخ واریزا ناقص است")
    return data


def verify_webhook(raw_body: bytes, signature: str) -> bool:
    secret = get_config()["webhook_secret"]
    if not secret or not signature:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


def _json(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def save_charge_link(charge_id: int, data: dict) -> None:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE charge_requests
                   SET method_key='variza', variza_slug=%s, variza_amount=%s,
                       status='waiting_receipt'
                   WHERE id=%s""",
                (data.get("slug"), int(data.get("amount") or 0), charge_id),
            )
            conn.commit()
    finally:
        conn.close()


def save_order_link(order_id: int, data: dict) -> None:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE service_orders
                   SET method_key='variza', variza_slug=%s, variza_amount=%s,
                       status='waiting_receipt'
                   WHERE id=%s""",
                (data.get("slug"), int(data.get("amount") or 0), order_id),
            )
            conn.commit()
    finally:
        conn.close()


def _credit_charge(charge_id: int, webhook: dict) -> Optional[dict]:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM charge_requests WHERE id=%s FOR UPDATE", (charge_id,))
            ch = cur.fetchone()
            if not ch:
                return None
            if ch.get("status") == "approved":
                ch["_newly_processed"] = False
                return ch
            if ch.get("method_key") != "variza" or ch.get("variza_slug") != webhook.get("slug"):
                raise RuntimeError("شناسه پرداخت واریزا با شارژ تطابق ندارد")
            if ch.get("status") not in ("waiting_receipt", "pending_review"):
                return ch
            cur.execute(
                "UPDATE bot_users SET balance=balance+%s, updated_at=NOW() WHERE telegram_id=%s",
                (int(ch["amount"]), int(ch["telegram_id"])),
            )
            cur.execute(
                """UPDATE charge_requests
                   SET status='approved', variza_attempt_code=%s, variza_amount=%s,
                       variza_delivery_id=%s, paid_at=NOW(), updated_at=NOW()
                   WHERE id=%s""",
                (str(webhook.get("attempt_code") or ""), int(webhook.get("amount") or 0),
                 str(webhook.get("delivery_id") or ""), charge_id),
            )
            conn.commit()
            cur.execute("SELECT * FROM charge_requests WHERE id=%s", (charge_id,))
            out = cur.fetchone()
            if out:
                out["_newly_processed"] = True
            return out
    finally:
        conn.close()


def _mark_order_paid(order_id: int, webhook: dict) -> Optional[dict]:
    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM service_orders WHERE id=%s FOR UPDATE", (order_id,))
            order = cur.fetchone()
            if not order:
                return None
            if order.get("status") in ("paid", "provisioned"):
                order["_newly_processed"] = False
                return order
            if order.get("method_key") != "variza" or order.get("variza_slug") != webhook.get("slug"):
                raise RuntimeError("شناسه پرداخت واریزا با سفارش تطابق ندارد")
            if order.get("status") not in ("waiting_receipt", "pending_payment", "pending_review"):
                return order
            wallet_used = int(order.get("wallet_used") or 0)
            if wallet_used:
                cur.execute(
                    "UPDATE bot_users SET balance=balance-%s, updated_at=NOW() WHERE telegram_id=%s AND balance >= %s",
                    (wallet_used, int(order["telegram_id"]), wallet_used),
                )
                if cur.rowcount != 1:
                    raise RuntimeError("موجودی کیف پول رزروشده کافی نیست")
            cur.execute(
                """UPDATE service_orders
                   SET status='paid', variza_attempt_code=%s, variza_amount=%s,
                       variza_delivery_id=%s, paid_at=NOW(), updated_at=NOW()
                   WHERE id=%s""",
                (str(webhook.get("attempt_code") or ""), int(webhook.get("amount") or 0),
                 str(webhook.get("delivery_id") or ""), order_id),
            )
            conn.commit()
            cur.execute("SELECT * FROM service_orders WHERE id=%s", (order_id,))
            out = cur.fetchone()
            if out:
                out["_newly_processed"] = True
            return out
    finally:
        conn.close()


def handle_webhook(payload: dict, delivery_id: str = "") -> dict:
    if payload.get("event") != "payment.paid" or payload.get("status") != "paid":
        return {"ok": True, "ignored": True}
    slug = str(payload.get("slug") or "").strip()
    if not slug:
        raise RuntimeError("Webhook بدون slug دریافت شد")

    conn = get_sync_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, telegram_id, amount, status FROM charge_requests WHERE variza_slug=%s LIMIT 1", (slug,))
            charge = cur.fetchone()
            cur.execute("SELECT id, telegram_id, amount, status FROM service_orders WHERE variza_slug=%s LIMIT 1", (slug,))
            order = cur.fetchone()
    finally:
        conn.close()

    event = dict(payload)
    event["delivery_id"] = delivery_id
    if charge:
        result = _credit_charge(int(charge["id"]), event)
        return {"ok": True, "type": "charge", "id": int(charge["id"]), "already_processed": not bool(result and result.get("_newly_processed"))}
    if order:
        result = _mark_order_paid(int(order["id"]), event)
        if result and result.get("_newly_processed") and result.get("status") == "paid":
            from services.provision import provision_order
            provision = provision_order(int(order["id"]))
            if not provision.get("ok"):
                raise RuntimeError(provision.get("error") or "ساخت سرویس بعد از پرداخت ناموفق بود")
            try:
                from db_growth import award_purchase_points, pay_referral_commission
                award_purchase_points(int(order["telegram_id"]), int(order["amount"]), int(order["id"]))
                pay_referral_commission(int(order["telegram_id"]), int(order["amount"]))
            except Exception as e:
                print("variza growth:", e)
            try:
                conn2 = get_sync_connection()
                with conn2.cursor() as cur2:
                    cur2.execute("UPDATE service_orders SET status='provisioned', updated_at=NOW() WHERE id=%s", (int(order["id"]),))
                    conn2.commit()
                conn2.close()
            except Exception as e:
                print("variza order final status:", e)
            return {"ok": True, "type": "order", "id": int(order["id"]), "provision": provision}
        return {"ok": True, "type": "order", "id": int(order["id"]), "already_processed": True}

    raise RuntimeError("پرداخت واریزا پیدا نشد")
