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

"""Versiyon-anahtarlı reader cache — bayatlamaz.

Cache anahtarı içerik sürümünü içerir; içerik değişince sürüm artar ve eski
anahtarlar terk edilir (TTL beklemeye gerek yok). Broker gerektirmez (LocMem)."""
from __future__ import annotations

from collections.abc import Callable

from django.core.cache import cache

from apps.core.models import SiteState


def content_version() -> int:
    return SiteState.version()


def cached_by_version(key: str, builder: Callable, ttl: int = 300):
    """`builder()` sonucunu sürüm-anahtarlı cache'ler. Sonuç picklable olmalı."""
    full = f"{key}:v{content_version()}"
    value = cache.get(full)
    if value is None:
        value = builder()
        cache.set(full, value, ttl)
    return value


def invalidate() -> int:
    """İçerik sürümünü artırır → tüm versiyon-anahtarlı cache'ler geçersizleşir."""
    return SiteState.bump()
