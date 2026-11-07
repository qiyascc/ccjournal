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
PeriodicPulseMiddleware — worker'sız kurulumlarda periyodik görevlerin kalp atışı.

Her istek geldiğinde (süreç başına en çok dakikada bir) periyodik kayıtları
kontrol eder; zamanı gelen görev varsa **daemon thread**'de çalıştırır — istek
hiçbir zaman bloklanmaz. Ayrı `run_worker` süreci çalışıyorsa görevleri büyük
olasılıkla o kapar; bu middleware yalnızca sigortadır (OJS Acron mantığı).
"""
from __future__ import annotations

import threading
import time

_last_check = 0.0
_CHECK_EVERY = 60.0
_lock = threading.Lock()
ENABLED = True


def _pulse():
    from .periodic import maybe_run_periodic
    from .queue import run_due
    try:
        maybe_run_periodic()
        run_due(limit=10)
    finally:
        from django.db import connections
        connections.close_all()


class PeriodicPulseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        global _last_check
        if not ENABLED:
            return self.get_response(request)
        now = time.monotonic()
        if now - _last_check >= _CHECK_EVERY:
            with _lock:
                if now - _last_check >= _CHECK_EVERY:
                    _last_check = now
                    threading.Thread(target=_pulse, daemon=True).start()
        return self.get_response(request)
