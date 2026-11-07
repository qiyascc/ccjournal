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
Tek komutla güvenli, yerinde yükseltme (OJS'in "upgrade" adımının karşılığı).

Kod güncellendikten sonra (git pull / dosya kopyalama) çalıştırılır:

    python manage.py upgrade

Sırasıyla: migrate (post_migrate seed'leri — roller, menüler, config — otomatik
tetiklenir) → e-posta şablonu seed'i → collectstatic. Idempotenttir; her deploy'da
güvenle çalıştırılabilir. systemd üniteleri ayrıca ExecStartPre ile migrate
çalıştırır, böylece migration'sız restart mümkün değildir.
"""
from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Upgrade in place: migrations + seeds + static files (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--no-static", action="store_true",
                            help="Skip collectstatic (dev / worker-only hosts).")

    def handle(self, *args, **opts):
        self.stdout.write("→ migrate")
        call_command("migrate", interactive=False, verbosity=1)
        self.stdout.write("→ seed_email_templates")
        call_command("seed_email_templates")
        if not opts["no_static"]:
            self.stdout.write("→ collectstatic")
            call_command("collectstatic", interactive=False, verbosity=0)
        self.stdout.write(self.style.SUCCESS("✓ Upgrade complete — safe to (re)start the service."))
