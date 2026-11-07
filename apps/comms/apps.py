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

from django.apps import AppConfig


class CommsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.comms"
    label = "comms"
    verbose_name = "Communication"

    def ready(self):
        from django.db.models.signals import post_migrate

        from . import receivers  # noqa: F401  (sinyalleri bağlar)

        def _seed(**kwargs):
            try:
                from apps.core.locales import CONTENT_LOCALES
                from .models import EmailTemplate
                from .seeding import seed
                seed(EmailTemplate, [c for c, _, _ in CONTENT_LOCALES])
            except Exception:
                pass
        post_migrate.connect(_seed, sender=self, dispatch_uid="seed_email_templates")
