# Factory: get panel API client by panel_type

from __future__ import annotations
from typing import Any, Union

from services.pasarguard import PasarGuardClient
from services.xui3 import XUI3Client


def get_panel_client(panel: dict) -> Union[PasarGuardClient, XUI3Client]:
    ptype = (panel.get("panel_type") or "pasarguard").lower().strip()
    base = panel.get("base_url") or ""
    user = panel.get("username") or ""
    pwd = panel.get("password") or ""
    api_key = panel.get("api_key") or panel.get("api_token") or ""
    if ptype in ("3x-ui", "3xui", "xui", "sanaei", "x-ui"):
        return XUI3Client(base, user, pwd, api_token=api_key, verify_ssl=False)
    return PasarGuardClient(base, user, pwd, verify_ssl=False)


def is_xui_panel(panel: dict) -> bool:
    ptype = (panel.get("panel_type") or "").lower().strip()
    return ptype in ("3x-ui", "3xui", "xui", "sanaei", "x-ui")
