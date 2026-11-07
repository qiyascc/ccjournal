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
Plugin kayıt defteri — keşif (discovery), yükleme ve enable durumu önbelleği.

Keşif: BASE_DIR/plugins/ altındaki her alt paket import edilir; paket bir `plugin`
örneği açığa çıkarmalıdır. Bulunan plugin'lerin register() çağrılarak hook'ları bağlanır
(hook'lar her zaman bağlı kalır; devre dışı plugin'lerin callback'leri çalışma anında atlanır).
"""
from __future__ import annotations

import importlib
import pkgutil

from django.conf import settings


class PluginRegistry:
    def __init__(self):
        self._plugins: dict[str, object] = {}
        self._enabled: dict[str, bool] | None = None
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        try:
            import plugins as plugins_pkg
        except Exception:
            return
        for mod in pkgutil.iter_modules(plugins_pkg.__path__):
            if mod.name.startswith("_"):
                continue
            try:
                module = importlib.import_module(f"plugins.{mod.name}")
                plugin = getattr(module, "plugin", None)
                if plugin is not None:
                    self.register_plugin(plugin)
            except Exception as e:
                if getattr(settings, "DEBUG", False):
                    print(f"[plugins] '{mod.name}' yüklenemedi: {e}")

    def register_plugin(self, plugin) -> None:
        if not getattr(plugin, "key", ""):
            raise ValueError("Plugin 'key' tanımlı olmalı.")
        self._plugins[plugin.key] = plugin
        plugin.register()

    def all(self):
        return list(self._plugins.values())

    def get(self, key):
        return self._plugins.get(key)

    def is_enabled(self, key: str) -> bool:
        return self._enabled_states().get(key, False)

    def _enabled_states(self) -> dict[str, bool]:
        if self._enabled is None:
            from .models import PluginState
            try:
                self._enabled = dict(
                    PluginState.objects.values_list("plugin_key", "enabled"))
            except Exception:
                return {}
        return self._enabled

    def invalidate(self) -> None:
        self._enabled = None


registry = PluginRegistry()
