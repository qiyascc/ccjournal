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


class AnnouncementsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.announcements"
    label = "announcements"
    verbose_name = "Announcements"
