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

from django.core.management.base import BaseCommand, CommandError

from apps.plugins.installer import InstallError, install_zip


class Command(BaseCommand):
    help = "Install a plugin from a .zip file path."

    def add_arguments(self, parser):
        parser.add_argument("zip_path")

    def handle(self, *args, **opts):
        try:
            with open(opts["zip_path"], "rb") as f:
                key = install_zip(f)
        except (InstallError, OSError) as e:
            raise CommandError(str(e))
        self.stdout.write(self.style.SUCCESS(f"Installed plugin '{key}'."))
