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
İş kuyruğu işçisi — broker gerektirmez.

Kullanım:
    python manage.py run_worker              # sürekli çalış (Ctrl-C / SIGTERM ile dur)
    python manage.py run_worker --once       # bir tur çalış ve çık (cron/CI için)
    python manage.py run_worker --interval 5 --batch 50

Üretimde plugins/runtime.py sidecar yöneticisiyle veya systemd ile başlatılabilir.
"""
from __future__ import annotations

import signal
import time

from django.core.management.base import BaseCommand

from apps.tasks.queue import run_due


class Command(BaseCommand):
    help = "DB-destekli iş kuyruğu işçisi (broker'sız)."

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=float, default=2.0,
                            help="Turlar arası bekleme (sn)")
        parser.add_argument("--batch", type=int, default=20,
                            help="Tur başına en fazla iş")
        parser.add_argument("--once", action="store_true",
                            help="Bir tur çalış ve çık")

    def handle(self, *args, **opts):
        self._running = True

        def _stop(*_):
            self._running = False

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

        from apps.tasks.periodic import maybe_run_periodic

        if opts["once"]:
            maybe_run_periodic()
            n = run_due(limit=opts["batch"])
            self.stdout.write(self.style.SUCCESS(f"processed {n} job(s)"))
            return

        self.stdout.write(self.style.SUCCESS("worker started (Ctrl-C to stop)"))
        while self._running:
            try:
                maybe_run_periodic()
                run_due(limit=opts["batch"])
            except Exception as exc:  # noqa: BLE001 — worker döngüsü asla çökmemeli
                self.stderr.write(f"worker loop error: {exc}")
            time.sleep(opts["interval"])
        self.stdout.write("worker stopped")
