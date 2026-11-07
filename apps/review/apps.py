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


class ReviewConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.review"
    label = "review"
    verbose_name = "Değerlendirme"

    def ready(self):
        from . import signals  # noqa: F401
