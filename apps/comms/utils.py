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

"""İletişim yardımcıları."""
from __future__ import annotations


def absolute_url(path: str) -> str:
    """Göreli yolu, config'teki site_url ile mutlak URL'ye çevirir.

    E-postaya giren HER link bundan geçmeli — göreli yol e-postada tıklanamaz.
    site_url ayarlanmamışsa yol olduğu gibi döner (en azından kopyalanabilir).
    """
    if not path or path.startswith(("http://", "https://")):
        return path
    try:
        from apps.configuration.services import Config
        base = (Config.get("general", "site_url", "") or "").rstrip("/")
    except Exception:
        base = ""
    return f"{base}{path}" if base else path
