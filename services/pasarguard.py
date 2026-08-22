# کلاینت API پاسارگارد (PasarGuard Panel)
# مستندات: https://github.com/PasarGuard/panel
# Auth: POST /api/admin/token (OAuth2 form)
# Stats: GET /api/system , /api/system/resources , /api/system/users

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse

import requests

# لیست APIهای مهم پاسارگارد برای توسعه آینده:
# ------------------------------------------------------------
# AUTH
#   POST /api/admin/token          → دریافت access_token
#   POST /api/admin/miniapp/token  → لاگین مینی‌اپ
#
# SYSTEM
#   GET  /api/system               → آمار کلی (CPU/RAM/Disk + کاربران)
#   GET  /api/system/resources     → فقط منابع سخت‌افزاری
#   GET  /api/system/users         → فقط آمار کاربران و ترافیک
#   GET  /api/workers/health       → سلامت workerها
#   GET  /api/inbounds             → لیست inboundها
#   GET  /api/inbounds/details     → جزئیات inbound
#
# USERS
#   GET  /api/users                → لیست کاربران
#   POST /api/user                 → ساخت کاربر
#   GET  /api/user/{username}      → جزئیات کاربر
#   PUT  /api/user/{username}      → ویرایش
#   DELETE /api/user/{username}    → حذف
#   (bulk enable/disable/reset/delete)
#
# NODES
#   GET/POST /api/nodes
#   GET /api/node/{id}/stats       → آمار لحظه‌ای نود
#
# GROUPS / HOSTS / CORES / TEMPLATES / SETTINGS
#   مسیرهای /api/group , /api/host , /api/core , /api/user_template , /api/settings
# ------------------------------------------------------------


def normalize_base_url(url: str) -> str:
    """
    آدرس پنل را به base URL تمیز تبدیل می‌کند.
    مثال:
      https://example.com:8000/dashboard  → https://example.com:8000
      https://example.com:8000/dashboard/ → https://example.com:8000
    """
    url = (url or "").strip().rstrip("/")
    if not url:
        raise ValueError("آدرس پنل خالی است")

    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url

    parsed = urlparse(url)
    if not parsed.netloc:
        raise ValueError("آدرس پنل نامعتبر است")

    # حذف مسیر dashboard و زیرمجموعه‌هایش
    path = parsed.path or ""
    path_lower = path.lower()
    for marker in ("/dashboard", "/login", "/admin"):
        idx = path_lower.find(marker)
        if idx >= 0:
            path = path[:idx]
            break

    path = path.rstrip("/")
    base = urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
    return base.rstrip("/")


class PasarGuardClient:
    """کلاینت همگام برای ارتباط با پنل پاسارگارد"""

    def __init__(self, base_url: str, username: str = "", password: str = "", timeout: int = 15, verify_ssl: bool = False):
        self.base_url = normalize_base_url(base_url)
        self.username = username
        self.password = password
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.token: Optional[str] = None

    def _headers(self) -> dict:
        h = {"Accept": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def login(self) -> str:
        """
        لاگین با username/password و دریافت JWT
        POST /api/admin/token  (application/x-www-form-urlencoded)
        """
        url = f"{self.base_url}/api/admin/token"
        data = {
            "username": self.username,
            "password": self.password,
            "grant_type": "password",
        }
        try:
            resp = requests.post(
                url,
                data=data,
                headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
        except requests.RequestException as e:
            raise ConnectionError(f"عدم اتصال به پنل: {e}") from e

        if resp.status_code == 401:
            raise PermissionError("نام کاربری یا رمز عبور پنل اشتباه است")
        if resp.status_code >= 400:
            detail = ""
            try:
                detail = resp.json().get("detail", resp.text[:200])
            except Exception:
                detail = resp.text[:200]
            raise RuntimeError(f"خطای لاگین ({resp.status_code}): {detail}")

        body = resp.json()
        token = body.get("access_token")
        if not token:
            raise RuntimeError("توکن از پنل دریافت نشد")
        self.token = token
        return token

    def _get(self, path: str) -> Any:
        if not self.token:
            self.login()
        url = f"{self.base_url}{path}"
        try:
            resp = requests.get(
                url,
                headers=self._headers(),
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
        except requests.RequestException as e:
            raise ConnectionError(f"خطا در دریافت داده: {e}") from e

        if resp.status_code == 401:
            # یک‌بار تلاش مجدد با لاگین تازه
            self.login()
            resp = requests.get(url, headers=self._headers(), timeout=self.timeout, verify=self.verify_ssl)

        if resp.status_code >= 400:
            detail = ""
            try:
                detail = resp.json().get("detail", resp.text[:200])
            except Exception:
                detail = resp.text[:200]
            raise RuntimeError(f"خطای API ({resp.status_code}): {detail}")

        return resp.json()

    def test_connection(self) -> dict:
        """تست اتصال: لاگین + دریافت آمار سیستم"""
        self.login()
        stats = self.get_system_stats()
        return {"ok": True, "base_url": self.base_url, "stats": stats}

    def get_system_stats(self) -> dict:
        """GET /api/system — آمار سخت‌افزار + کاربران"""
        return self._get("/api/system")

    def get_system_resources(self) -> dict:
        """GET /api/system/resources"""
        return self._get("/api/system/resources")

    def get_system_users(self) -> dict:
        """GET /api/system/users"""
        return self._get("/api/system/users")
