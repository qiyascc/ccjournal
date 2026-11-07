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

from apps.search.services import SearchIndex


class Command(BaseCommand):
    help = "Rebuild the full-text search index from published publications."

    def handle(self, *args, **opts):
        n = SearchIndex.rebuild()
        self.stdout.write(self.style.SUCCESS(f"Indexed {n} publication(s)."))
