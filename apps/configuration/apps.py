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
from django.db.models.signals import post_migrate


class ConfigurationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.configuration"
    label = "configuration"
    verbose_name = "Configuration"

    def ready(self):
        from .services import seed_from_file
        post_migrate.connect(lambda **kw: seed_from_file(), sender=self)
