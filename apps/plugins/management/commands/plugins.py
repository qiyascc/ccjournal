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

from apps.plugins.models import PluginState
from apps.plugins.registry import registry


class Command(BaseCommand):
    help = "List discovered plugins and sync them into the database."

    def handle(self, *args, **opts):
        for p in registry.all():
            state, _ = PluginState.objects.get_or_create(
                plugin_key=p.key, defaults={"enabled": False})
            flag = "ON " if state.enabled else "off"
            self.stdout.write(f"[{flag}] {p.key:20} {p.category:12} {p.name} v{p.version}")
        if not registry.all():
            self.stdout.write("No plugins discovered in plugins/.")
