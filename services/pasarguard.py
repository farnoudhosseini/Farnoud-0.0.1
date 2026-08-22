# کلاینت API پاسارگارد (PasarGuard Panel)

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse

import requests


def normalize_base_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if not url:
        raise ValueError("آدرس پنل خالی است")
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        raise ValueError("آدرس پنل نامعتبر است")
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


def gb_to_bytes(gb) -> int:
    try:
        v = float(gb)
    except (TypeError, ValueError):
        return 0
    if v <= 0:
        return 0
    return int(v * 1024 ** 3)


def bytes_to_gb(b) -> float:
    try:
        return round(int(b or 0) / (1024 ** 3), 2)
    except (TypeError, ValueError):
        return 0.0


def parse_expire(value) -> Optional[str]:
    """تبدیل تاریخ فرم به ISO UTC برای API — خالی = نامحدود"""
    if value is None or value == "" or value == "0":
        return None
    if isinstance(value, (int, float)):
        if int(value) <= 0:
            return None
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
    s = str(value).strip()
    if not s:
        return None
    # datetime-local: 2026-08-22T15:30
    try:
        if "T" in s:
            dt = datetime.fromisoformat(s)
        else:
            dt = datetime.strptime(s, "%Y-%m-%d")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


class PasarGuardClient:
    def __init__(self, base_url: str, username: str = "", password: str = "", timeout: int = 20, verify_ssl: bool = False):
        self.base_url = normalize_base_url(base_url)
        self.username = username
        self.password = password
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.token: Optional[str] = None

    def _headers(self, json_body: bool = False) -> dict:
        h = {"Accept": "application/json"}
        if json_body:
            h["Content-Type"] = "application/json"
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def login(self) -> str:
        url = f"{self.base_url}/api/admin/token"
        data = {"username": self.username, "password": self.password, "grant_type": "password"}
        try:
            resp = requests.post(
                url, data=data,
                headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout, verify=self.verify_ssl,
            )
        except requests.RequestException as e:
            raise ConnectionError(f"عدم اتصال به پنل: {e}") from e
        if resp.status_code == 401:
            raise PermissionError("نام کاربری یا رمز عبور پنل اشتباه است")
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text[:200])
            except Exception:
                detail = resp.text[:200]
            raise RuntimeError(f"خطای لاگین ({resp.status_code}): {detail}")
        token = resp.json().get("access_token")
        if not token:
            raise RuntimeError("توکن از پنل دریافت نشد")
        self.token = token
        return token

    def _request(self, method: str, path: str, **kwargs) -> Any:
        if not self.token:
            self.login()
        url = f"{self.base_url}{path}"
        headers = self._headers(json_body="json" in kwargs)
        try:
            resp = requests.request(method, url, headers=headers, timeout=self.timeout, verify=self.verify_ssl, **kwargs)
        except requests.RequestException as e:
            raise ConnectionError(f"خطای شبکه: {e}") from e
        if resp.status_code == 401:
            self.login()
            headers = self._headers(json_body="json" in kwargs)
            resp = requests.request(method, url, headers=headers, timeout=self.timeout, verify=self.verify_ssl, **kwargs)
        if resp.status_code == 204:
            return None
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text[:300])
            except Exception:
                detail = resp.text[:300]
            raise RuntimeError(f"خطای API ({resp.status_code}): {detail}")
        if not resp.content:
            return None
        return resp.json()

    def test_connection(self) -> dict:
        self.login()
        stats = self.get_system_stats()
        return {"ok": True, "base_url": self.base_url, "stats": stats}

    def get_system_stats(self) -> dict:
        return self._request("GET", "/api/system") or {}

    def get_groups(self) -> list:
        """GET /api/groups"""
        data = self._request("GET", "/api/groups")
        if isinstance(data, dict):
            return data.get("groups") or data.get("items") or []
        if isinstance(data, list):
            return data
        return []

    def get_users(self, offset: int = 0, limit: int = 50, search: str = None) -> dict:
        """GET /api/users"""
        params = {"offset": offset, "limit": limit}
        if search:
            params["search"] = search
        # requests params
        if not self.token:
            self.login()
        url = f"{self.base_url}/api/users"
        headers = self._headers()
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=self.timeout, verify=self.verify_ssl)
        except requests.RequestException as e:
            raise ConnectionError(f"خطای شبکه: {e}") from e
        if resp.status_code == 401:
            self.login()
            resp = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout, verify=self.verify_ssl)
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text[:300])
            except Exception:
                detail = resp.text[:300]
            raise RuntimeError(f"خطای API ({resp.status_code}): {detail}")
        data = resp.json()
        if isinstance(data, list):
            return {"users": data, "total": len(data)}
        return data

    def get_user(self, username: str) -> dict:
        return self._request("GET", f"/api/user/{username}") or {}

    def create_user(self, payload: dict) -> dict:
        """POST /api/user"""
        return self._request("POST", "/api/user", json=payload) or {}

    def modify_user(self, username: str, payload: dict) -> dict:
        """PUT /api/user/{username}"""
        return self._request("PUT", f"/api/user/{username}", json=payload) or {}

    def delete_user(self, username: str) -> None:
        """DELETE /api/user/{username}"""
        self._request("DELETE", f"/api/user/{username}")

    def build_user_payload(
        self,
        username: str = None,
        status: str = "active",
        data_limit_gb=None,
        expire=None,
        group_ids=None,
        hwid_limit=None,
        note: str = None,
        on_hold_expire_duration=None,
        for_create: bool = True,
    ) -> dict:
        payload = {}
        if for_create:
            if not username:
                raise ValueError("نام کاربری الزامی است")
            payload["username"] = username.strip()
        if status:
            payload["status"] = status
        # data_limit: 0 = unlimited
        if data_limit_gb is not None and str(data_limit_gb).strip() != "":
            payload["data_limit"] = gb_to_bytes(data_limit_gb)
        else:
            if for_create:
                payload["data_limit"] = 0
        exp = parse_expire(expire)
        if exp is not None:
            payload["expire"] = exp
        elif for_create:
            payload["expire"] = None
        if group_ids is not None:
            if isinstance(group_ids, str):
                group_ids = [int(x) for x in group_ids.split(",") if x.strip().isdigit()]
            payload["group_ids"] = list(group_ids) if group_ids else []
        elif for_create:
            payload["group_ids"] = []
        if hwid_limit is not None and str(hwid_limit).strip() != "":
            try:
                payload["hwid_limit"] = int(hwid_limit)
            except ValueError:
                pass
        if note is not None:
            payload["note"] = note[:500] if note else None

        # on_hold بدون مدت‌زمان در پاسارگارد 422 می‌دهد
        if status == "on_hold":
            duration = on_hold_expire_duration
            if duration is None or str(duration).strip() == "":
                duration = 30 * 24 * 3600  # پیش‌فرض ۳۰ روز (ثانیه)
            try:
                duration = int(duration)
            except (TypeError, ValueError):
                duration = 30 * 24 * 3600
            if duration <= 0:
                duration = 30 * 24 * 3600
            payload["on_hold_expire_duration"] = duration
        return payload
