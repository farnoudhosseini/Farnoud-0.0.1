# کلاینت API پنل 3x-ui (MHSanaei / ثنایی)
# Auth:
#   1) Bearer API Token  → مستقیم، بدون login
#   2) username/password → CSRF + /login + session cookie
# URL نمونه: https://example.com:2053/secretpath

from __future__ import annotations

import json
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
from urllib.parse import urlparse, urlunparse

import requests

# نام‌های رایج کوکی نشست در نسخه‌های مختلف 3x-ui
COOKIE_NAMES = ("3x-ui", "session", "lang")


def normalize_xui_base(url: str) -> str:
    """
    آدرس پایه پنل با webBasePath.
    مثال ورودی: https://example.com:2053/mysecret
    یا: https://example.com:2053/mysecret/panel/inbounds  → برش تا قبل /panel
    """
    url = (url or "").strip().rstrip("/")
    if not url:
        raise ValueError("آدرس پنل خالی است")
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        raise ValueError("آدرس پنل نامعتبر است")
    path = (parsed.path or "").rstrip("/")
    lower = path.lower()
    # فقط پسوندهای UI را جدا کن؛ خود webBasePath را نگه دار
    for marker in ("/panel/inbounds", "/panel/api", "/xui/", "/login"):
        idx = lower.find(marker)
        if idx >= 0:
            path = path[:idx].rstrip("/")
            break
    # اگر دقیقاً به /panel ختم شد
    if path.lower().endswith("/panel"):
        path = path[: -len("/panel")].rstrip("/")
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
    3x-ui client.
    - اگر api_token باشد: فقط Bearer، بدون یوزر/پسورد
    - وگرنه: CSRF → login → cookie
    """

    def __init__(
        self,
        base_url: str,
        username: str = "",
        password: str = "",
        api_token: str = "",
        timeout: int = 30,
        verify_ssl: bool = False,
    ):
        self.base_url = normalize_xui_base(base_url)
        self.username = (username or "").strip()
        self.password = password or ""
        self.api_token = (api_token or "").strip()
        # اگر با Bearer شروع شده بود، پاک کن
        if self.api_token.lower().startswith("bearer "):
            self.api_token = self.api_token[7:].strip()
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self._logged_in = False
        self._csrf_token: Optional[str] = None

        if not self.api_token and not (self.username and self.password):
            raise ValueError("برای 3x-ui یا API Token یا نام‌کاربری و رمز عبور لازم است")

    def _url(self, path: str) -> str:
        path = path if path.startswith("/") else f"/{path}"
        return f"{self.base_url}{path}"

    def _auth_headers(self) -> dict:
        h = {"Accept": "application/json"}
        if self.api_token:
            h["Authorization"] = f"Bearer {self.api_token}"
        elif self._csrf_token:
            h["X-CSRF-Token"] = self._csrf_token
        return h

    def _fetch_csrf(self) -> Optional[str]:
        """بعضی نسخه‌ها CSRF می‌خواهند؛ اگر نبود نادیده می‌گیریم."""
        try:
            r = self.session.get(
                self._url("/csrf-token"),
                headers={"Accept": "application/json"},
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
            if r.status_code >= 400:
                return None
            data = r.json() if r.content else {}
            token = data.get("obj") if isinstance(data, dict) else None
            if isinstance(token, str) and token:
                self._csrf_token = token
                return token
        except Exception:
            pass
        return None

    def login(self) -> bool:
        if self.api_token:
            # با توکن نیازی به login نیست
            self._logged_in = True
            return True

        self._csrf_token = None
        csrf = self._fetch_csrf()
        headers = {"Accept": "application/json"}
        if csrf:
            headers["X-CSRF-Token"] = csrf

        data = {
            "username": self.username,
            "password": self.password,
        }
        r = self.session.post(
            self._url("/login"),
            data=data,
            headers=headers,
            timeout=self.timeout,
            verify=self.verify_ssl,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"لاگین 3x-ui ناموفق (HTTP {r.status_code}). آدرس/مسیر پنل را چک کنید.")

        try:
            body = r.json()
        except Exception:
            body = {}

        if isinstance(body, dict) and body.get("success") is False:
            raise RuntimeError(body.get("msg") or "نام کاربری یا رمز اشتباه است")

        # کوکی نشست
        got_cookie = False
        for name in COOKIE_NAMES:
            if self.session.cookies.get(name):
                got_cookie = True
                break
        if not got_cookie:
            # هر کوکی غیرخالی
            if list(self.session.cookies):
                got_cookie = True
        if not got_cookie and body.get("success") is not True:
            raise RuntimeError(
                "لاگین 3x-ui: نشست برقرار نشد. مسیر (webBasePath) و یوزر/رمز را بررسی کنید."
            )

        self._logged_in = True
        return True

    def ensure_auth(self):
        if not self._logged_in:
            self.login()

    def _request(self, method: str, path: str, **kwargs) -> Any:
        self.ensure_auth()
        headers = self._auth_headers()
        headers.update(kwargs.pop("headers", {}) or {})
        url = self._url(path)
        r = self.session.request(
            method, url, headers=headers, timeout=self.timeout, verify=self.verify_ssl, **kwargs
        )
        # یک‌بار retry بعد از 401 با لاگین دوباره (فقط وقتی توکن نیست)
        if r.status_code == 401 and not self.api_token:
            self._logged_in = False
            self.login()
            headers = self._auth_headers()
            r = self.session.request(
                method, url, headers=headers, timeout=self.timeout, verify=self.verify_ssl, **kwargs
            )
        if r.status_code >= 400:
            raise RuntimeError(f"3x-ui {method} {path}: HTTP {r.status_code} — {(r.text or '')[:250]}")
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
        """تست واقعی: لاگین/توکن + لیست اینباند."""
        self.login()
        self.list_inbounds()
        return True

    def get_system_stats(self) -> dict:
        for path in ("/panel/api/server/status", "/server/status"):
            try:
                obj = self._request("GET", path)
                return obj if isinstance(obj, dict) else {"raw": obj}
            except Exception as e:
                last = e
        return {"error": str(last) if last else "status unavailable"}

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
        # 3x-ui 3.7.0+ client lifecycle / HWID (optional — older panels ignore unknown keys)
        limit_hwid: int = 0,
        reset_day: int = 0,
        reset_max: int = 0,
        traffic_reset: str = "never",
        traffic_reset_day: int = 1,
        start_on_first_connect: bool = False,
    ) -> dict:
        email = email or _rand_email()
        sub_id = sub_id or _rand_sub_id()
        client_uuid = client_uuid or str(uuid.uuid4())
        total_bytes = gb_to_bytes(total_gb)
        # اولین اتصال: در بسیاری از بیلدهای ثنایی، expiryTime منفی = مدت (ms) بعد از اولین اتصال
        if start_on_first_connect and days and days > 0:
            exp_ms = -int(int(days) * 86400 * 1000)
        elif days and days > 0:
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
            "tgId": int(tg_id or 0),
            "subId": sub_id,
            "reset": 0,
        }
        # 3.7.0 fields — safe defaults match previous behaviour
        try:
            lh = int(limit_hwid or 0)
            if lh > 0:
                client_obj["limitHwid"] = lh
        except (TypeError, ValueError):
            pass
        try:
            rd = int(reset_day or 0)
            if 1 <= rd <= 31:
                client_obj["resetDay"] = rd
        except (TypeError, ValueError):
            pass
        try:
            rm = int(reset_max or 0)
            if rm > 0:
                client_obj["resetMax"] = rm
        except (TypeError, ValueError):
            pass
        tr = (traffic_reset or "never").strip().lower()
        if tr in ("hourly", "daily", "weekly", "monthly"):
            client_obj["trafficReset"] = tr
            try:
                client_obj["trafficResetDay"] = max(1, min(31, int(traffic_reset_day or 1)))
            except (TypeError, ValueError):
                client_obj["trafficResetDay"] = 1

        settings = json.dumps({"clients": [client_obj]}, ensure_ascii=False)
        payload = {"id": int(inbound_id), "settings": settings}
        try:
            result = self._request("POST", "/panel/api/inbounds/addClient", json=payload)
        except Exception:
            payload2 = {"inboundIds": [int(inbound_id)], "client": client_obj}
            result = self._request("POST", "/panel/api/clients/add", json=payload2)

        return {
            "email": email,
            "subId": sub_id,
            "id": client_uuid,
            "uuid": client_uuid,
            "limitIp": limit_ip,
            "limitHwid": client_obj.get("limitHwid", 0),
            "totalGB": total_bytes,
            "expiryTime": exp_ms,
            "inbound_id": inbound_id,
            "result": result,
        }

    def update_client(self, client_id: str, inbound_id: int, client_obj: dict) -> Any:
        """Update a single client. Prefer full inbound update (most compatible across 3x-ui forks)."""
        email = (client_obj.get("email") or "").strip()
        # Ensure required fields
        if not client_obj.get("id"):
            client_obj["id"] = str(client_id)
        if email and not client_obj.get("email"):
            client_obj["email"] = email

        errors = []

        # Method A: replace client inside inbound settings and POST /panel/api/inbounds/update
        try:
            return self._update_client_via_inbound(int(inbound_id), str(client_id), client_obj, email)
        except Exception as e:
            errors.append(f"inbound-update: {e}")

        # Method B: classic updateClient paths
        settings = json.dumps({"clients": [client_obj]}, ensure_ascii=False)
        payload = {"id": int(inbound_id), "settings": settings}
        paths = [
            f"/panel/api/inbounds/updateClient/{client_id}",
            f"/panel/inbound/updateClient/{client_id}",
            f"/panel/api/inbounds/updateClient/{inbound_id}/{client_id}",
        ]
        if email and email != str(client_id):
            paths += [
                f"/panel/api/inbounds/updateClient/{email}",
                f"/panel/inbound/updateClient/{email}",
            ]
        for path in paths:
            try:
                return self._request("POST", path, json=payload)
            except Exception as e:
                errors.append(f"{path}: {e}")

        raise RuntimeError("updateClient failed: " + " | ".join(errors[:4]))

    def _update_client_via_inbound(self, inbound_id: int, client_id: str, client_obj: dict, email: str = "") -> Any:
        """Load inbound, replace matching client, save full inbound (works on MHSanaei when updateClient 404s)."""
        ib = self.get_inbound(int(inbound_id))
        if not ib:
            # try find from list
            for item in self.list_inbounds():
                if int(item.get("id") or 0) == int(inbound_id):
                    ib = item
                    break
        if not ib:
            raise RuntimeError(f"inbound {inbound_id} not found")

        settings_raw = ib.get("settings")
        if isinstance(settings_raw, str):
            try:
                settings_obj = json.loads(settings_raw)
            except Exception:
                settings_obj = {}
        elif isinstance(settings_raw, dict):
            settings_obj = dict(settings_raw)
        else:
            settings_obj = {}

        clients = list(settings_obj.get("clients") or [])
        replaced = False
        for i, c in enumerate(clients):
            cid = str(c.get("id") or c.get("uuid") or "")
            cem = (c.get("email") or "").strip()
            if cid == str(client_id) or (email and cem == email):
                # merge preserving unknown keys
                merged = dict(c)
                merged.update(client_obj)
                # keep id stable
                merged["id"] = c.get("id") or client_obj.get("id") or client_id
                if email:
                    merged["email"] = email
                clients[i] = merged
                replaced = True
                break
        if not replaced:
            clients.append(client_obj)
        settings_obj["clients"] = clients

        # Build update payload — keep original inbound fields
        payload = dict(ib)
        payload["settings"] = json.dumps(settings_obj, ensure_ascii=False)
        # Some panels expect settings as object; try string first (standard 3x-ui)
        for path in ("/panel/api/inbounds/update", "/panel/inbound/update", "/panel/api/inbounds/update/" + str(inbound_id)):
            try:
                return self._request("POST", path, json=payload)
            except Exception as e:
                last = e
                continue
        # retry with settings as dict
        payload["settings"] = settings_obj
        return self._request("POST", "/panel/api/inbounds/update", json=payload)

    def delete_client(self, inbound_id: int, client_id: str) -> Any:
        return self._request("POST", f"/panel/api/inbounds/{int(inbound_id)}/delClient/{client_id}")

    def reset_client_traffic(self, inbound_id: int, email: str) -> Any:
        return self._request(
            "POST", f"/panel/api/inbounds/{int(inbound_id)}/resetClientTraffic/{email}"
        )

    def get_all_settings(self) -> dict:
        """تنظیمات پنل شامل subPort / subPath / subURI / subDomain"""
        for method, path in (
            ("GET", "/panel/api/setting/all"),
            ("POST", "/panel/api/setting/all"),
            ("POST", "/panel/setting/all"),
            ("GET", "/panel/setting/all"),
        ):
            try:
                obj = self._request(method, path)
                if isinstance(obj, dict) and obj:
                    return obj
            except Exception:
                continue
        return {}

    def get_client_sub_links(self, email: str = "", sub_id: str = "") -> list:
        """تلاش برای گرفتن لینک‌های آماده از API مدرن"""
        paths = []
        if email:
            paths += [
                ("GET", f"/panel/api/clients/get/{email}"),
                ("GET", f"/panel/api/clients/{email}"),
                ("GET", f"/panel/api/inbounds/getClientTraffics/{email}"),
            ]
        if sub_id:
            paths += [
                ("GET", f"/panel/api/clients/subLinks/{sub_id}"),
                ("GET", f"/panel/api/clients/getSubLinks/{sub_id}"),
            ]
        for method, path in paths:
            try:
                obj = self._request(method, path)
                if not obj:
                    continue
                # استخراج URL از ساختارهای رایج
                links = []
                if isinstance(obj, dict):
                    for k in ("subUrl", "subLink", "subscriptionUrl", "subscription_url", "url", "link"):
                        v = obj.get(k)
                        if isinstance(v, str) and v.startswith("http"):
                            links.append(v)
                    for k in ("subLinks", "links", "urls"):
                        v = obj.get(k)
                        if isinstance(v, list):
                            for item in v:
                                if isinstance(item, str) and item.startswith("http"):
                                    links.append(item)
                                elif isinstance(item, dict):
                                    for kk in ("url", "link", "subUrl"):
                                        if isinstance(item.get(kk), str) and item[kk].startswith("http"):
                                            links.append(item[kk])
                    # nested client
                    c = obj.get("client") or obj.get("obj") or {}
                    if isinstance(c, dict):
                        for k in ("subUrl", "subLink", "subscriptionUrl"):
                            v = c.get(k)
                            if isinstance(v, str) and v.startswith("http"):
                                links.append(v)
                if links:
                    return links
            except Exception:
                continue
        return []

    def subscription_url(self, sub_id: str, email: str = "") -> str:
        """
        لینک ساب واقعی طبق تنظیمات پنل ثنایی.
        اولویت:
          1) لینک آماده از API کلاینت
          2) subURI از تنظیمات + subId
          3) ساخت از subDomain/host + subPort + subPath + subId
        """
        if not sub_id:
            return ""

        # 1) API
        try:
            links = self.get_client_sub_links(email=email, sub_id=sub_id)
            for u in links:
                if "/sub" in u or "sub" in u.lower():
                    return u
            if links:
                return links[0]
        except Exception:
            pass

        # 2) تنظیمات پنل
        settings = {}
        try:
            settings = self.get_all_settings() or {}
        except Exception:
            settings = {}

        sub_uri = (settings.get("subURI") or settings.get("subUri") or "").strip()
        if sub_uri:
            # subURI معمولاً مثل https://domain:2096/sub/ است
            if sub_uri.endswith(sub_id):
                return sub_uri
            if not sub_uri.endswith("/"):
                sub_uri += "/"
            return sub_uri + sub_id

        sub_path = settings.get("subPath") or "/sub/"
        if not str(sub_path).startswith("/"):
            sub_path = "/" + str(sub_path)
        if not str(sub_path).endswith("/"):
            sub_path = str(sub_path) + "/"

        sub_port = settings.get("subPort") or settings.get("sub_port") or 2096
        try:
            sub_port = int(sub_port)
        except Exception:
            sub_port = 2096

        sub_domain = (settings.get("subDomain") or settings.get("sub_domain") or "").strip()
        # scheme: اگر ساب TLS داشته باشد از https
        has_cert = bool(settings.get("subCertFile") or settings.get("subKeyFile"))
        # از base_url پنل scheme و host بگیر
        from urllib.parse import urlparse
        parsed = urlparse(self.base_url)
        scheme = parsed.scheme or "https"
        if has_cert:
            scheme = "https"
        host = sub_domain or parsed.hostname or ""
        if not host:
            return f"{self.base_url.rstrip('/')}{sub_path}{sub_id}"

        # پورت پیش‌فرض را در URL ننویس اگر 443/80 باشد
        if (scheme == "https" and sub_port == 443) or (scheme == "http" and sub_port == 80):
            return f"{scheme}://{host}{sub_path}{sub_id}"
        return f"{scheme}://{host}:{sub_port}{sub_path}{sub_id}"


    def _client_to_user_row(self, client: dict, inbound: dict = None) -> dict:
        """نرمال‌سازی کلاینت 3x-ui به شکل مشابه پاسارگارد برای وب‌پنل"""
        email = client.get("email") or client.get("username") or ""
        total = int(client.get("totalGB") or client.get("total") or 0)
        up = int(client.get("up") or 0)
        down = int(client.get("down") or 0)
        # clientStats sometimes separate
        used = up + down
        if client.get("used_traffic") is not None:
            used = int(client.get("used_traffic") or 0)
        exp = client.get("expiryTime") or client.get("expire") or 0
        try:
            exp_i = int(exp)
        except Exception:
            exp_i = 0
        expire_str = None
        if exp_i and exp_i > 0:
            # ms or sec
            ts = exp_i / 1000 if exp_i > 10_000_000_000 else exp_i
            try:
                from datetime import datetime, timezone
                expire_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
            except Exception:
                expire_str = str(exp_i)
        enable = client.get("enable", True)
        return {
            "username": email,
            "email": email,
            "status": "active" if enable else "disabled",
            "used_traffic": used,
            "data_limit": total,
            "expire": expire_str,
            "hwid_limit": client.get("limitIp") if client.get("limitIp") else None,
            "subId": client.get("subId") or "",
            "id": client.get("id") or client.get("uuid") or "",
            "inbound_id": (inbound or {}).get("id"),
            "inbound_remark": (inbound or {}).get("remark") or "",
            "enable": enable,
        }

    def get_users(self, offset: int = 0, limit: int = 200, search: str = None) -> dict:
        """لیست کلاینت‌ها از همه اینباندها — سازگار با وب‌پنل"""
        users = []
        seen = set()
        for ib in self.list_inbounds():
            settings = ib.get("settings")
            if isinstance(settings, str):
                try:
                    settings = json.loads(settings)
                except Exception:
                    settings = {}
            clients = (settings or {}).get("clients") or []
            # traffic from clientStats
            stats_map = {}
            for st in (ib.get("clientStats") or []):
                em = st.get("email")
                if em:
                    stats_map[em] = st
            for c in clients:
                email = c.get("email") or ""
                if not email or email in seen:
                    continue
                if search and search.lower() not in email.lower():
                    continue
                st = stats_map.get(email) or {}
                merged = dict(c)
                if st:
                    merged["up"] = st.get("up", 0)
                    merged["down"] = st.get("down", 0)
                    if st.get("total"):
                        merged["totalGB"] = st.get("total")
                row = self._client_to_user_row(merged, ib)
                users.append(row)
                seen.add(email)
        total = len(users)
        users = users[offset: offset + limit]
        return {"users": users, "total": total}

    def get_user(self, username: str) -> dict:
        found = self.find_client_in_inbounds(username)
        if not found:
            return {}
        c = found.get("client") or {}
        ib = found.get("inbound") or {}
        st = self.get_client_traffics(username) or {}
        merged = dict(c)
        if isinstance(st, dict):
            merged["up"] = st.get("up", merged.get("up", 0))
            merged["down"] = st.get("down", merged.get("down", 0))
            if st.get("total"):
                merged["totalGB"] = st.get("total")
        row = self._client_to_user_row(merged, ib)
        row["subscription_url"] = self.subscription_url(row.get("subId") or "", email=username)
        return row


    def modify_user(self, username: str, payload: dict) -> dict:
        """Apply status/volume/expire/hwid changes for 3x-ui client identified by email."""
        found = self.find_client_in_inbounds(username)
        if not found:
            raise RuntimeError(f"کلاینت یافت نشد: {username}")
        c = dict(found.get("client") or {})
        ib = found.get("inbound") or {}
        inbound_id = found.get("inbound_id") or ib.get("id")
        if not inbound_id:
            raise RuntimeError("inbound_id نامشخص")

        # status
        if payload.get("status") is not None:
            st = str(payload["status"]).lower()
            c["enable"] = st in ("active", "enabled", "on", "1", "true")

        # IP limit (limitIp) — legacy hwid_limit maps here
        if "hwid_limit" in payload or "limitIp" in payload:
            lim = payload.get("limitIp", payload.get("hwid_limit"))
            c["limitIp"] = int(lim or 0)

        # 3.7.0 subscription HWID limit (limitHwid) — independent of IP limit
        if "limit_hwid" in payload or "limitHwid" in payload:
            try:
                c["limitHwid"] = int(payload.get("limitHwid", payload.get("limit_hwid")) or 0)
            except (TypeError, ValueError):
                pass

        # Calendar renew / auto-renew cap / traffic reset (3.7.0)
        if "reset_day" in payload or "resetDay" in payload:
            try:
                rd = int(payload.get("resetDay", payload.get("reset_day")) or 0)
                c["resetDay"] = rd if 0 <= rd <= 31 else 0
            except (TypeError, ValueError):
                pass
        if "reset_max" in payload or "resetMax" in payload:
            try:
                c["resetMax"] = max(0, int(payload.get("resetMax", payload.get("reset_max")) or 0))
            except (TypeError, ValueError):
                pass
        if "traffic_reset" in payload or "trafficReset" in payload:
            tr = str(payload.get("trafficReset", payload.get("traffic_reset")) or "never").strip().lower()
            if tr in ("never", "hourly", "daily", "weekly", "monthly"):
                c["trafficReset"] = tr
        if "traffic_reset_day" in payload or "trafficResetDay" in payload:
            try:
                c["trafficResetDay"] = max(1, min(31, int(payload.get("trafficResetDay", payload.get("traffic_reset_day")) or 1)))
            except (TypeError, ValueError):
                pass

        # volume — 3x-ui totalGB is in bytes on most builds
        if payload.get("data_limit") is not None:
            c["totalGB"] = int(payload["data_limit"] or 0)

        # expire ISO → ms
        if payload.get("expire"):
            try:
                from datetime import datetime
                s = str(payload["expire"]).replace("Z", "+00:00")
                dt = datetime.fromisoformat(s)
                c["expiryTime"] = int(dt.timestamp() * 1000)
            except Exception:
                pass

        # direct ms expire
        if payload.get("expiryTime") is not None:
            c["expiryTime"] = int(payload["expiryTime"])

        client_id = c.get("id") or c.get("uuid")
        if not client_id:
            try:
                tr = self.get_client_traffics(username) or {}
                client_id = tr.get("id") or tr.get("uuid")
                if tr.get("inboundId") and not inbound_id:
                    inbound_id = tr.get("inboundId")
            except Exception:
                pass
        if not client_id:
            raise RuntimeError(f"UUID کلاینت یافت نشد برای {username}")

        c["id"] = str(client_id)
        c["email"] = username
        # ensure enable key exists
        if "enable" not in c:
            c["enable"] = True

        self.update_client(str(client_id), int(inbound_id), c)
        return c

    def delete_user(self, username: str) -> None:
        found = self.find_client_in_inbounds(username)
        if not found:
            raise RuntimeError(f"کلاینت یافت نشد: {username}")
        ib = found.get("inbound") or {}
        c = found.get("client") or {}
        inbound_id = found.get("inbound_id") or ib.get("id")
        client_id = c.get("id") or c.get("password") or username
        if not inbound_id:
            raise RuntimeError("inbound_id نامشخص")
        self.delete_client(int(inbound_id), str(client_id))

    def find_client_in_inbounds(self, email: str) -> Optional[dict]:
        for ib in self.list_inbounds():
            settings = ib.get("settings")
            if isinstance(settings, str):
                try:
                    settings = json.loads(settings)
                except Exception:
                    settings = {}
            for c in (settings or {}).get("clients") or []:
                if (c.get("email") or "") == email:
                    return {"inbound": ib, "client": c, "inbound_id": ib.get("id")}
        tr = self.get_client_traffics(email)
        if tr:
            return {"inbound": None, "client": tr, "inbound_id": tr.get("inboundId")}
        return None
