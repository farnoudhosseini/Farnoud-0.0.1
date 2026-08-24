# ساخت سرویس VPN روی پاسارگارد و آماده‌سازی پیام تحویل

from __future__ import annotations

import io
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from database import get_panel_by_id, get_setting_sync
from db_products import get_product, get_order, update_order
from db_users import get_bot_user, render_template, set_template, get_template
from services.pasarguard import PasarGuardClient, gb_to_bytes

def fix_subscription_url(panel_base: str, sub_link: str) -> str:
    """اگر لینک نسبی /sub/... بود، base پنل را جلو می‌چسباند."""
    if not sub_link:
        return ""
    s = str(sub_link).strip()
    if s.startswith("http://") or s.startswith("https://"):
        return s
    base = (panel_base or "").rstrip("/")
    if not base:
        return s
    if not s.startswith("/"):
        s = "/" + s
    return base + s



def _rand_username(prefix: str = "u") -> str:
    alphabet = string.ascii_lowercase + string.digits
    return prefix + "".join(secrets.choice(alphabet) for _ in range(8))


def ensure_service_template():
    body = (
        "📦 سرویس [service_volume] گیگابایت - [service_expiration] روز\n"
        "📊 وضعیت: [status]\n"
        "📱 تعداد دستگاه‌های متصل به این سرویس: [hwid_s]\n"
        "🔢 شماره سرویس: [service_id]\n"
        "⏳ زمان باقی‌مانده: [service_expiration] روز\n"
        "💾 حجم باقی‌مانده: [service_volume] گیگابایت\n"
        "🔗 لینک اتصال:\n[subscription_link]\n"
        "ℹ️ توجه: آموزش اتصال به سرویس‌ها را می‌توانید در بخش «مرکز آموزش» ببینید.\n"
        "🔐 برای تغییر رمز و قطع دسترسی افراد متصل به پروکسی روی دکمه زیر کلیک کنید\n"
        "[channel_id]"
    )
    current = get_template("service_delivered") or ""
    # اگر خالی است یا نسخه قدیمی بدون ایموجی است، آپدیت کن
    if not current.strip() or not current.strip().startswith("📦"):
        set_template("service_delivered", body, title="پیام تحویل سرویس")


def provision_order(order_id: int) -> dict:
    """
    ساخت کاربر روی پاسارگارد برای سفارش و برگرداندن داده پیام + QR.
    returns: {ok, text, qr_bytes, error, user_data}
    """
    ensure_service_template()
    order = get_order(order_id)
    if not order:
        return {"ok": False, "error": "سفارش یافت نشد"}
    product = get_product(order["product_id"])
    panel = get_panel_by_id(order["panel_id"])
    if not product or not panel:
        return {"ok": False, "error": "محصول یا پنل نامعتبر"}

    # اول از محصول، بعد اگر روی سفارش override باشد جایگزین می‌شود
    # (برای تست رایگان و هدیه باشگاه ضروری است)
    volume_gb = float(product.get("volume_gb") or 0)
    days = int(product.get("duration_days") or 30)
    try:
        ov_vol = order.get("volume_gb_override")
        if ov_vol is not None and str(ov_vol).strip() != "":
            volume_gb = float(ov_vol)
    except (TypeError, ValueError):
        pass
    try:
        ov_days = order.get("duration_days_override")
        if ov_days is not None and str(ov_days).strip() != "":
            days = int(ov_days)
    except (TypeError, ValueError):
        pass
    # HWID از محصول — خالی/None = نامحدود
    hwid_raw = product.get("hwid_limit")
    hwid = None
    if hwid_raw is not None and str(hwid_raw).strip() != "":
        try:
            hwid = int(hwid_raw)
            if hwid <= 0:
                hwid = None
        except (TypeError, ValueError):
            hwid = None

    from services.panel_client import get_panel_client, is_xui_panel

    # Deterministic username makes retries idempotent: the same order maps to the same VPN identity.
    # Existing orders with vpn_username are never recreated.
    username = (order.get("vpn_username") or f"fn{int(order_id):08d}")[:100]
    if order.get("vpn_username") and order.get("status") == "provisioned":
        try:
            existing_panel = get_panel_by_id(order["panel_id"])
            existing_client = get_panel_client(existing_panel)
            existing_full = existing_client.get_user(order["vpn_username"]) or {}
            raw = existing_full.get("subscription_url") or existing_full.get("subscription_link") or ""
            if not raw and existing_full.get("subscription_token"):
                raw = f"/sub/{existing_full['subscription_token']}"
            sub_link = fix_subscription_url(existing_panel.get("base_url") or "", raw)
            return {"ok": True, "text": "", "qr_bytes": make_qr_png(sub_link) if sub_link else None,
                    "user_data": existing_full, "subscription_link": sub_link,
                    "vpn_username": order["vpn_username"], "idempotent": True}
        except Exception:
            pass
    expire_dt = datetime.now(timezone.utc) + timedelta(days=days)

    # پیکربندی گروه/اینباند از محصول (تنظیم ادمین)
    panel_cfg = {}
    try:
        panel_cfg = (product.get("panel_config") or {}).get(int(panel["id"])) or {}
    except Exception:
        panel_cfg = {}
    # override پروتکل از سفارش (تست رایگان / هدیه و ...)
    try:
        import json
        raw_po = order.get("protocol_override")
        if raw_po:
            if isinstance(raw_po, str):
                po = json.loads(raw_po)
            else:
                po = raw_po
            if isinstance(po, dict) and po:
                panel_cfg = dict(panel_cfg or {})
                if po.get("inbound_ids"):
                    panel_cfg["inbound_ids"] = list(po["inbound_ids"])
                if po.get("group_ids"):
                    panel_cfg["group_ids"] = list(po["group_ids"])
    except Exception as e:
        print("protocol_override:", e)

    if is_xui_panel(panel):
        # ---- 3x-ui ----
        xui = get_panel_client(panel)
        inbound_ids = list(panel_cfg.get("inbound_ids") or [])
        if not inbound_ids:
            try:
                choices = xui.list_inbound_choices()
                if choices:
                    inbound_ids = [choices[0]["id"]]
            except Exception as e:
                return {"ok": False, "error": f"لیست اینباند: {e}"}
        if not inbound_ids:
            return {"ok": False, "error": "برای این محصول اینباندی در پنل تنظیم نشده"}
        limit_ip = int(hwid) if hwid else 0
        created = None
        last_err = None
        # روی همه اینباندهای انتخاب‌شده کلاینت بساز (همان email/subId)
        shared_email = username
        shared_sub = None
        shared_uuid = None
        for iid in inbound_ids:
            try:
                created = xui.add_client(
                    inbound_id=int(iid),
                    email=shared_email,
                    total_gb=volume_gb if volume_gb > 0 else 0,
                    days=days if days > 0 else 0,
                    limit_ip=limit_ip,
                    tg_id=int(order.get("telegram_id") or 0),
                    client_uuid=shared_uuid,
                    sub_id=shared_sub,
                )
                shared_sub = created.get("subId") or shared_sub
                shared_uuid = created.get("uuid") or created.get("id") or shared_uuid
                shared_email = created.get("email") or shared_email
            except Exception as e:
                last_err = e
        if not created:
            return {"ok": False, "error": f"ساخت کلاینت 3x-ui: {last_err}"}
        sub_id = created.get("subId") or shared_sub or ""
        sub_link = xui.subscription_url(sub_id, email=created.get("email") or username)
        full = {
            "username": created.get("email") or username,
            "email": created.get("email") or username,
            "status": "active",
            "limitIp": limit_ip,
            "subId": sub_id,
            "id": created.get("id"),
            "inbound_ids": inbound_ids,
            "subscription_url": sub_link,
        }
        status = "active"
        hwid_s = limit_ip if limit_ip else "نامحدود"
        service_id = full.get("id") or order_id
        remain_gb = volume_gb
    else:
        # ---- PasarGuard ----
        client = PasarGuardClient(panel["base_url"], panel["username"], panel["password"], verify_ssl=False)
        group_ids = list(panel_cfg.get("group_ids") or [])
        if not group_ids:
            try:
                groups = client.get_groups()
                if groups:
                    group_ids = [groups[0].get("id") or groups[0]["id"]]
            except Exception:
                group_ids = []

        payload = client.build_user_payload(
            username=username,
            status="active",
            data_limit_gb=volume_gb if volume_gb > 0 else 0,
            expire=expire_dt.isoformat(),
            group_ids=group_ids,
            hwid_limit=hwid,
            note=f"order#{order_id} tg:{order['telegram_id']}",
            for_create=True,
        )
        try:
            # If a previous attempt created the remote user but failed before DB commit,
            # recover it instead of creating a duplicate.
            try:
                existing_remote = client.get_user(username)
            except Exception:
                existing_remote = None
            created = existing_remote or client.create_user(payload)
        except Exception as e:
            return {"ok": False, "error": f"ساخت اکانت: {e}"}

        try:
            full = client.get_user(created.get("username") or username)
        except Exception:
            full = created or {}

        raw_sub = (
            full.get("subscription_url")
            or full.get("subscription_link")
            or created.get("subscription_url")
            or full.get("link")
            or ""
        )
        if not raw_sub and full.get("subscription_token"):
            raw_sub = f"/sub/{full.get('subscription_token')}"
        sub_link = fix_subscription_url(panel.get("base_url") or "", raw_sub)
        status = full.get("status") or "active"
        hwid_s = full.get("hwid_limit")
        if hwid_s is None or hwid_s == 0:
            hwid_s = "نامحدود"
        service_id = full.get("id") or created.get("id") or order_id
        used = full.get("used_traffic") or 0
        limit = full.get("data_limit") or 0
        remain_gb = volume_gb
        if limit and limit > 0:
            remain_gb = round(max(0, (limit - used) / (1024 ** 3)), 2)

    channel = get_setting_sync("channel_id", "") or get_setting_sync("support_channel", "") or "—"

    vars_ = {
        "service_volume": remain_gb if remain_gb else volume_gb,
        "service_expiration": days,
        "status": status,
        "hwid_s": hwid_s,
        "service_id": service_id,
        "subscription_link": sub_link,
        "channel_id": channel,
        "username": full.get("username") or username,
        "product_name": product.get("name") or "",
        "panel_name": panel.get("name") or "",
    }
    text = render_template("service_delivered", vars_)
    if not text.strip():
        text = (
            f"📦 سرویس {vars_['service_volume']} گیگابایت - {days} روز\n"
            f"📊 وضعیت: {status}\n"
            f"📱 تعداد دستگاه‌های متصل به این سرویس: {hwid_s}\n"
            f"🔢 شماره سرویس: {service_id}\n"
            f"⏳ زمان باقی‌مانده: {days} روز\n"
            f"💾 حجم باقی‌مانده: {vars_['service_volume']} گیگابایت\n"
            f"🔗 لینک اتصال:\n{sub_link}\n"
            f"ℹ️ توجه: آموزش اتصال به سرویس‌ها را می‌توانید در بخش «مرکز آموزش» ببینید.\n"
            f"🔐 برای تغییر رمز و قطع دسترسی افراد متصل به پروکسی روی دکمه زیر کلیک کنید\n"
            f"{channel}"
        )

    update_order(
        order_id,
        status="provisioned",
        vpn_username=full.get("username") or username,
    )

    qr_bytes = make_qr_png(sub_link) if sub_link else None
    return {
        "ok": True,
        "text": text,
        "qr_bytes": qr_bytes,
        "user_data": full,
        "subscription_link": sub_link,
        "vpn_username": full.get("username") or username,
    }


def make_qr_png(data: str) -> Optional[bytes]:
    if not data:
        return None
    try:
        import qrcode
        from qrcode.image.pil import PilImage
        qr = qrcode.QRCode(version=1, box_size=8, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        print(f"QR error: {e}")
        return None


async def send_service_to_user(bot, telegram_id: int, result: dict):
    try:
        from handlers.group_reports import send_report
        if result.get("ok"):
            await send_report(
                bot, "sales",
                f"✅ سرویس تحویل شد\nکاربر: <code>{telegram_id}</code>\nیوزرنیم: <code>{result.get('vpn_username') or '—'}</code>",
            )
        else:
            await send_report(bot, "errors", f"❌ خطا در ساخت سرویس: {result.get('error')}")
    except Exception:
        pass

    """ارسال پیام تحویل + QR"""
    if not result.get("ok"):
        await bot.send_message(telegram_id, f"❌ خطا در ساخت سرویس: {result.get('error')}")
        return
    text = result["text"]
    qr = result.get("qr_bytes")
    if qr:
        from telegram import InputFile
        await bot.send_photo(
            telegram_id,
            photo=InputFile(io.BytesIO(qr), filename="service-qr.png"),
            caption=text[:1024] if len(text) > 1024 else text,
        )
        if len(text) > 1024:
            await bot.send_message(telegram_id, text)
    else:
        await bot.send_message(telegram_id, text)
