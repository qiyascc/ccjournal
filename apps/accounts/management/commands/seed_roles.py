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

from django.core.management.base import BaseCommand

from apps.accounts.roles import seed_roles


class Command(BaseCommand):
    help = "Create/refresh all role groups and their permissions (idempotent)."

    def handle(self, *args, **opts):
        n = seed_roles()
        self.stdout.write(self.style.SUCCESS(f"Seeded {n} role groups."))
