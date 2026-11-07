# ==========================================================
#
# █▀█ █ █▄█ ▄▀█ █▀  █▀▀ █▀▀
# ▀▀█ █ ░█░ █▀█ ▄█  █▄▄ █▄▄
#
# Project     : CC Journal
# Developed by: Qiyas CC
# Copyright © 2026 Qiyas CC
# All Rights Reserved.
# ==========================================================

"""WhatsApp sidecar istemcisi — Node.js servisini başlatır/durdurur/sorgular.

Plugin etkinleştirilince Node.js sidecar (Baileys) bir kez başlatılır; QR taranınca
oturum kalıcı olur. Bu modül Django ile sidecar arasındaki tek köprüdür (yerel HTTP).
"""
from __future__ import annotations

import secrets
from pathlib import Path


SERVICE_NAME = "whatsapp"
SIDECAR_DIR = Path(__file__).resolve().parent / "sidecar"
DEFAULT_PORT = 8782


def _setting(key, default=None):
    from apps.plugins.models import PluginSetting
    row = PluginSetting.objects.filter(plugin_key="whatsapp", journal=None, key=key).first()
    return row.value if row else default


def _set(key, value):
    from apps.plugins.models import PluginSetting
    PluginSetting.objects.update_or_create(
        plugin_key="whatsapp", journal=None, key=key, defaults={"value": value})


def _token() -> str:
    tok = _setting("token")
    if not tok:
        tok = secrets.token_urlsafe(24)
        _set("token", tok)
    return tok


def _port() -> int:
    try:
        return int(_setting("port", DEFAULT_PORT))
    except (TypeError, ValueError):
        return DEFAULT_PORT


def _base_url() -> str:
    return f"http://127.0.0.1:{_port()}"


def start() -> None:
    """Sidecar'ı başlatır (idempotent). node_modules yoksa açıklayıcı hata loglar."""
    from apps.plugins import runtime
    if runtime.is_running(SERVICE_NAME):
        return
    node_modules = SIDECAR_DIR / "node_modules"
    if not node_modules.exists():
        import logging
        logging.getLogger("whatsapp").error(
            "WhatsApp sidecar dependencies missing. Run: cd whatsapp_service && npm install")
        return
    env = {
        "WA_PORT": str(_port()),
        "WA_TOKEN": _token(),
        "WA_AUTH_DIR": str(SIDECAR_DIR / "auth"),
    }
    try:
        from apps.comms.hook_views import hook_secret
        from apps.configuration.services import Config
        base = (Config.get("channels", "hook_base", "") or "").strip().rstrip("/") \
            or "http://127.0.0.1:9444"
        env["WA_HOOK_URL"] = f"{base}/hooks/channel-reply/"
        env["WA_HOOK_SECRET"] = hook_secret()
    except Exception:
        import logging
        logging.getLogger("whatsapp").warning(
            "inbound hook not configured; quick replies disabled", exc_info=True)
    if _setting("mock") == "1":
        env["WA_MOCK"] = "1"
    if _setting("mock_connect") == "1":
        env["WA_MOCK_CONNECT"] = "1"
    runtime.start(SERVICE_NAME, ["node", "server.js"], cwd=str(SIDECAR_DIR), env=env)


def stop() -> None:
    from apps.plugins import runtime
    runtime.stop(SERVICE_NAME)


def is_running() -> bool:
    from apps.plugins import runtime
    return runtime.is_running(SERVICE_NAME)


def status() -> dict:
    """Sidecar durumunu döndürür: {running, status, qr, me, lastError}."""
    if not is_running():
        return {"running": False, "status": "stopped", "qr": None, "me": None}
    import requests
    try:
        r = requests.get(f"{_base_url()}/status", headers={"X-WA-Token": _token()}, timeout=4)
        data = r.json()
        data["running"] = True
        return data
    except Exception as e:  # noqa: BLE001
        return {"running": True, "status": "unreachable", "qr": None, "me": None,
                "lastError": str(e)}


def send(number: str, message: str) -> tuple[bool, str]:
    """Tek bir numaraya WhatsApp mesajı gönderir. (ok, hata) döner."""
    if not number:
        return False, "no number"
    if not is_running():
        return False, "sidecar not running"
    import requests
    try:
        r = requests.post(f"{_base_url()}/send",
                          headers={"X-WA-Token": _token()},
                          json={"number": number, "message": message}, timeout=10)
        if r.status_code == 200:
            return True, ""
        return False, r.json().get("error", f"http {r.status_code}")
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def logout() -> None:
    """Oturumu kapatır (yeni QR için)."""
    if not is_running():
        return
    import requests
    try:
        requests.post(f"{_base_url()}/logout", headers={"X-WA-Token": _token()}, timeout=5)
    except Exception:
        pass
