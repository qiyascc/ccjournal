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

from apps.navigation.services import seed_menus_if_empty


class Command(BaseCommand):
    help = "Seed default navigation menus if none exist."

    def handle(self, *args, **opts):
        n = seed_menus_if_empty()
        self.stdout.write(self.style.SUCCESS(f"Created {n} default menu item(s)."))
