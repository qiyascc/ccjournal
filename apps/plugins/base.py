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

"""
Plugin tabanı + kategoriler (OJS plugin kategorilerine paralel).

Bir plugin paketi `plugins/<ad>/__init__.py` içinde `plugin = <Plugin alt sınıfı>()`
açığa çıkarır. `register()` içinde hook'larına abone olur.
"""
from __future__ import annotations


class PluginCategory:
    GENERIC = "generic"
    THEME = "theme"
    BLOCK = "block"
    GATEWAY = "gateway"
    IMPORTEXPORT = "importexport"
    OAI_METADATA = "oaiMetadata"
    PUB_ID = "pubId"
    REPORT = "report"
    AUTH = "auth"
    CITATION = "citation"


class Plugin:
    key: str = ""
    name: str = ""
    version: str = "1.0.0"
    category: str = PluginCategory.GENERIC
    description: str = ""
    author: str = ""

    def register(self) -> None:
        """hooks.register(...) çağrılarını burada yap. Alt sınıf override eder."""

    def on_enable(self) -> None:
        """Plugin etkinleştirildiğinde çağrılır (ör. sidecar süreç başlat)."""

    def on_disable(self) -> None:
        """Plugin devre dışı bırakıldığında çağrılır (ör. sidecar süreç durdur)."""

    def is_enabled(self) -> bool:
        from .registry import registry
        return registry.is_enabled(self.key)

    def get_setting(self, key: str, default=None, *, journal=None):
        from .models import PluginSetting
        try:
            row = PluginSetting.objects.get(plugin_key=self.key, journal=journal, key=key)
            return row.value
        except PluginSetting.DoesNotExist:
            return default

    def set_setting(self, key: str, value, *, journal=None) -> None:
        from .models import PluginSetting
        PluginSetting.objects.update_or_create(
            plugin_key=self.key, journal=journal, key=key, defaults={"value": value}
        )

    def __str__(self) -> str:
        return f"{self.name or self.key} v{self.version}"
