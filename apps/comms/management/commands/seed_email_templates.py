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

from apps.comms.models import EmailTemplate
from apps.comms.seeding import seed
from apps.core.locales import CONTENT_LOCALES


class Command(BaseCommand):
    help = "Seed default email templates for every supported locale (idempotent)."

    def handle(self, *args, **opts):
        n = seed(EmailTemplate, [c for c, _, _ in CONTENT_LOCALES])
        self.stdout.write(self.style.SUCCESS(f"Created {n} missing template row(s)."))
