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


class NavigationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.navigation"
    label = "navigation"
    verbose_name = "Navigation"

    def ready(self):
        from .services import seed_menus_if_empty
        post_migrate.connect(lambda **kw: seed_menus_if_empty(), dispatch_uid="seed_menus")
