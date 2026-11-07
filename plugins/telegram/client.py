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

"""Telegram bot sidecar istemcisi — polling sürecini başlatır/durdurur.

Bildirim GÖNDERME işi burada değil (onu channel.py doğrudan Telegram API ile yapar);
bu istemci yalnız komut işleyen polling botu yönetir.
"""
from __future__ import annotations

from pathlib import Path

SERVICE_NAME = "telegram"
SIDECAR_DIR = Path(__file__).resolve().parent / "sidecar"


def _setting(key, default=None):
    from apps.plugins.models import PluginSetting
    row = PluginSetting.objects.filter(plugin_key="telegram", journal=None, key=key).first()
    return row.value if row else default


def set_setting(key, value):
    from apps.plugins.models import PluginSetting
    PluginSetting.objects.update_or_create(
        plugin_key="telegram", journal=None, key=key, defaults={"value": value})


def token() -> str:
    return _setting("token", "") or ""


def start() -> None:
    """Polling botunu başlatır (token varsa ve sidecar bağımlılıkları kuruluysa)."""
    import sys
    from apps.plugins import runtime
    if not token():
        import logging
        logging.getLogger("telegram").info("Telegram token not set; bot not started.")
        return
    if runtime.is_running(SERVICE_NAME):
        return
    env = {"TG_TOKEN": token()}
    runtime.start(SERVICE_NAME, [sys.executable, "bot.py"], cwd=str(SIDECAR_DIR), env=env)


def stop() -> None:
    from apps.plugins import runtime
    runtime.stop(SERVICE_NAME)


def restart() -> None:
    stop(); start()


def is_running() -> bool:
    from apps.plugins import runtime
    return runtime.is_running(SERVICE_NAME)


def _api(method: str, **params):
    """Telegram Bot API çağrısı (token gerektirir)."""
    import requests
    tok = token()
    if not tok:
        return None
    try:
        r = requests.post(f"https://api.telegram.org/bot{tok}/{method}",
                          json=params, timeout=10)
        return r.json()
    except Exception:
        return None


def bot_username() -> str:
    """Bot kullanıcı adını döndürür (deep-link için). Token yoksa boş."""
    data = _api("getMe")
    if data and data.get("ok"):
        return data["result"].get("username", "")
    return ""


def send(chat_id: str, message: str) -> tuple[bool, str]:
    """Tek bir chat'e mesaj gönderir (bot çalışmasa da token yeterli)."""
    if not chat_id:
        return False, "no chat id"
    data = _api("sendMessage", chat_id=chat_id, text=message, parse_mode="Markdown")
    if data is None:
        return False, "telegram api unreachable"
    if data.get("ok"):
        return True, ""
    return False, str(data.get("description", "send failed"))
