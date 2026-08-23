# کلاینت API پنل 3x-ui (Sanaei)
# Auth: session cookie via /login  OR  Authorization: Bearer <api_token>
# Docs: https://github.com/MHSanaei/3x-ui

from __future__ import annotations

import json
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

import requests


def normalize_xui_base(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if not url:
        raise ValueError("آدرس پنل خالی است")
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        raise ValueError("آدرس پنل نامعتبر است")
    path = (parsed.path or "").rstrip("/")
    # strip common UI tails
    lower = path.lower()
    for marker in ("/panel/inbounds", "/panel/", "/xui/", "/login"):
        idx = lower.find(marker.rstrip("/"))
        if idx > 0:
            path = path[:idx]
            break
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


def _rand_email(prefix: str = "fn") -> str:
    alphabet = string.ascii_lowercase + string.digits
    return prefix + "".join(secrets.choice(alphabet) for _ in range(10))


def _rand_sub_id(n: int = 16) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


class XUI3Client:
    """
    3x-ui (MHSanaei) API client.
    - Login with username/password → session cookie
    - Or Bearer API token (Settings → Security → API Token)
    """

    def __init__(
        self,
        base_url: str,
        username: str = "",
        password: str = "",
        api_token: str = "",
        timeout: int = 25,
        verify_ssl: bool = False,
    ):
        self.base_url = normalize_xui_base(base_url)
        self.username = username or ""
        self.password = password or ""
        self.api_token = (api_token or "").strip()
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self._logged_in = False

    def _headers(self) -> dict:
        h = {"Accept": "application/json"}
        if self.api_token:
            h["Authorization"] = f"Bearer {self.api_token}"
        return h

    def login(self) -> bool:
        if self.api_token:
            self._logged_in = True
            return True
        if not self.username or not self.password:
            raise RuntimeError("برای 3x-ui یا API Token یا نام‌کاربری/رمز لازم است")
        url = f"{self.base_url}/login"
        r = self.session.post(
            url,
            data={"username": self.username, "password": self.password},
            headers={"Accept": "application/json"},
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"لاگین 3x-ui ناموفق: HTTP {r.status_code}")
        try:
            data = r.json()
        except Exception:
            data = {}
        if data.get("success") is False:
            raise RuntimeError(data.get("msg") or "لاگین 3x-ui ناموفق")
        self._logged_in = True
        return True

    def ensure_auth(self):
        if not self._logged_in:
            self.login()

    def _request(self, method: str, path: str, **kwargs) -> Any:
        self.ensure_auth()
        if not path.startswith("/"):
            path = "/" + path
        url = self.base_url + path
        headers = self._headers()
        headers.update(kwargs.pop("headers", {}) or {})
        r = self.session.request(
            method, url, headers=headers, timeout=self.timeout, verify=self.verify_ssl, **kwargs
        )
        if r.status_code == 401 and not self.api_token:
            self._logged_in = False
            self.login()
            r = self.session.request(
                method, url, headers=headers, timeout=self.timeout, verify=self.verify_ssl, **kwargs
            )
        if r.status_code >= 400:
            raise RuntimeError(f"3x-ui {method} {path}: HTTP {r.status_code} {r.text[:300]}")
        try:
            data = r.json()
        except Exception:
            return r.text
        if isinstance(data, dict) and data.get("success") is False:
            raise RuntimeError(data.get("msg") or "خطای 3x-ui")
        if isinstance(data, dict) and "obj" in data:
            return data["obj"]
        return data

    def test_connection(self) -> bool:
        self.login()
        # try list inbounds as health check
        self.list_inbounds()
        return True

    def get_system_stats(self) -> dict:
        try:
            return self._request("GET", "/panel/api/server/status") or {}
        except Exception:
            try:
                return self._request("GET", "/server/status") or {}
            except Exception as e:
                return {"error": str(e)}

    def list_inbounds(self) -> List[dict]:
        obj = self._request("GET", "/panel/api/inbounds/list")
        if isinstance(obj, list):
            return obj
        if isinstance(obj, dict) and isinstance(obj.get("inbounds"), list):
            return obj["inbounds"]
        return []

    def get_inbound(self, inbound_id: int) -> Optional[dict]:
        return self._request("GET", f"/panel/api/inbounds/get/{int(inbound_id)}")

    def list_inbound_choices(self) -> List[dict]:
        """Simplified list for bot UI: id, remark, protocol, port, enable"""
        out = []
        for ib in self.list_inbounds():
            if not ib.get("enable", True):
                continue
            out.append({
                "id": ib.get("id"),
                "remark": ib.get("remark") or f"inbound-{ib.get('id')}",
                "protocol": ib.get("protocol") or "",
                "port": ib.get("port"),
                "enable": ib.get("enable", True),
            })
        return out

    def get_client_traffics(self, email: str) -> Optional[dict]:
        try:
            return self._request("GET", f"/panel/api/inbounds/getClientTraffics/{email}")
        except Exception:
            return None

    def add_client(
        self,
        inbound_id: int,
        email: str = None,
        total_gb: float = 0,
        days: int = 30,
        limit_ip: int = 0,
        tg_id: int = 0,
        enable: bool = True,
        client_uuid: str = None,
        sub_id: str = None,
        flow: str = "",
    ) -> dict:
        """
        Add client to one inbound (classic addClient API).
        total_gb: 0 = unlimited
        limit_ip: 0 = unlimited (IP Limit / Fail2Ban related)
        expiry: milliseconds unix; 0 = unlimited
        """
        email = email or _rand_email()
        sub_id = sub_id or _rand_sub_id()
        client_uuid = client_uuid or str(uuid.uuid4())
        total_bytes = gb_to_bytes(total_gb)
        if days and days > 0:
            exp_ms = int((datetime.now(timezone.utc) + timedelta(days=int(days))).timestamp() * 1000)
        else:
            exp_ms = 0

        client_obj = {
            "id": client_uuid,
            "flow": flow or "",
            "email": email,
            "limitIp": int(limit_ip or 0),
            "totalGB": int(total_bytes),
            "expiryTime": exp_ms,
            "enable": bool(enable),
            "tgId": str(tg_id or ""),
            "subId": sub_id,
            "reset": 0,
        }
        # Trojan uses password field instead of id in some versions
        settings = json.dumps({"clients": [client_obj]}, ensure_ascii=False)
        payload = {"id": int(inbound_id), "settings": settings}
        try:
            result = self._request("POST", "/panel/api/inbounds/addClient", json=payload)
        except Exception:
            # newer clients API
            payload2 = {
                "inboundIds": [int(inbound_id)],
                "client": client_obj,
            }
            result = self._request("POST", "/panel/api/clients/add", json=payload2)

        return {
            "email": email,
            "subId": sub_id,
            "id": client_uuid,
            "uuid": client_uuid,
            "limitIp": limit_ip,
            "totalGB": total_bytes,
            "expiryTime": exp_ms,
            "inbound_id": inbound_id,
            "result": result,
        }

    def update_client(self, client_id: str, inbound_id: int, client_obj: dict) -> Any:
        settings = json.dumps({"clients": [client_obj]}, ensure_ascii=False)
        payload = {"id": int(inbound_id), "settings": settings}
        return self._request("POST", f"/panel/api/inbounds/updateClient/{client_id}", json=payload)

    def delete_client(self, inbound_id: int, client_id: str) -> Any:
        return self._request("POST", f"/panel/api/inbounds/{int(inbound_id)}/delClient/{client_id}")

    def reset_client_traffic(self, inbound_id: int, email: str) -> Any:
        return self._request(
            "POST", f"/panel/api/inbounds/{int(inbound_id)}/resetClientTraffic/{email}"
        )

    def set_client_enable(self, inbound_id: int, email: str, enable: bool, client_meta: dict = None) -> Any:
        """Enable/disable client by re-pushing client config."""
        meta = client_meta or {}
        client_obj = {
            "id": meta.get("id") or meta.get("uuid") or str(uuid.uuid4()),
            "email": email,
            "enable": bool(enable),
            "limitIp": int(meta.get("limitIp") or 0),
            "totalGB": int(meta.get("totalGB") or 0),
            "expiryTime": int(meta.get("expiryTime") or 0),
            "tgId": str(meta.get("tgId") or ""),
            "subId": meta.get("subId") or "",
            "flow": meta.get("flow") or "",
            "reset": 0,
        }
        cid = client_obj["id"]
        return self.update_client(cid, inbound_id, client_obj)

    def subscription_url(self, sub_id: str) -> str:
        if not sub_id:
            return ""
        # default path /sub/{subId} — panel may use custom sub path
        return f"{self.base_url}/sub/{sub_id}"

    def find_client_in_inbounds(self, email: str) -> Optional[dict]:
        """Search all inbounds for client by email. Returns {inbound, client}."""
        for ib in self.list_inbounds():
            settings = ib.get("settings")
            if isinstance(settings, str):
                try:
                    settings = json.loads(settings)
                except Exception:
                    settings = {}
            clients = (settings or {}).get("clients") or []
            for c in clients:
                if (c.get("email") or "") == email:
                    return {"inbound": ib, "client": c, "inbound_id": ib.get("id")}
        # traffic endpoint fallback
        tr = self.get_client_traffics(email)
        if tr:
            return {"inbound": None, "client": tr, "inbound_id": tr.get("inboundId")}
        return None
