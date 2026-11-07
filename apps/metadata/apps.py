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


class MetadataConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.metadata"
    label = "metadata"
    verbose_name = "Metadata / Dışa Aktarım"
