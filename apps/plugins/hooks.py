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
Hook kayıt defteri — OJS HookRegistry karşılığı.

İki tür hook:
  * do_action(name, **kw)        -> bildirim tipi (dönüş yok)
  * apply_filters(name, value, **kw) -> değeri zincirden geçirip dönüştürür

Plugin'ler `register()` içinde hooks.register(...) çağırır. Devre dışı plugin'lerin
callback'leri çalışma anında atlanır (yeniden başlatma gerekmez).
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable


class HookRegistry:
    def __init__(self):
        self._hooks: dict[str, list[tuple[int, object, Callable]]] = defaultdict(list)

    def register(self, name: str, callback: Callable, *, plugin=None, priority: int = 10) -> None:
        self._hooks[name].append((priority, plugin, callback))
        self._hooks[name].sort(key=lambda x: x[0])

    def _active(self, name: str):
        for _prio, plugin, cb in self._hooks.get(name, []):
            if plugin is None or plugin.is_enabled():
                yield cb

    def do_action(self, name: str, **kwargs) -> None:
        for cb in self._active(name):
            cb(**kwargs)

    def apply_filters(self, name: str, value, **kwargs):
        for cb in self._active(name):
            value = cb(value, **kwargs)
        return value

    def registered_names(self) -> list[str]:
        return sorted(self._hooks.keys())


hooks = HookRegistry()
