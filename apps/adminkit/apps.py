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


class AdminKitConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.adminkit"
    label = "adminkit"
    verbose_name = "Admin Kit"

    def ready(self):
        from .upgrade import upgrade_admins
        upgrade_admins()
