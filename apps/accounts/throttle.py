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

"""Giriş denemesi kısıtlama — cache tabanlı, bağımlılıksız (django-axes'siz).

(ip, e-posta) çifti başına LIMIT başarısız deneme → WINDOW sn kilit. Başarılı
giriş sayacı sıfırlar. locmem cache'te süreç-yereldir (gunicorn worker başına);
paylaşımlı cache kurulursa otomatik olarak küme-genelinde çalışır.
"""
from __future__ import annotations

from django.core.cache import cache

LIMIT = 5
WINDOW = 15 * 60


def _keys(request, username: str) -> list[str]:
    ip = (request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
          or request.META.get("REMOTE_ADDR", "?"))
    u = (username or "").strip().lower()
    return [f"loginfail:ip:{ip}", f"loginfail:user:{u}"] if u else [f"loginfail:ip:{ip}"]


def register_failure(request, username: str) -> None:
    for k in _keys(request, username):
        try:
            added = cache.add(k, 1, WINDOW)
            if not added:
                cache.incr(k)
        except ValueError:
            cache.set(k, 1, WINDOW)


def reset(request, username: str) -> None:
    cache.delete_many(_keys(request, username))


def is_locked(request, username: str) -> bool:
    return any((cache.get(k) or 0) >= LIMIT for k in _keys(request, username))
