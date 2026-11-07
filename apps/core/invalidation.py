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

"""Menü/sayfa değişince reader cache sürümünü artıran sinyaller.

(Yayın/sayı değişimleri servis katmanında açıkça bump edilir.)"""
from __future__ import annotations

from django.db.models.signals import post_delete, post_save


def _bump(sender, **kwargs):
    from apps.core.models import SiteState
    SiteState.bump()


def connect() -> None:
    from apps.navigation.models import MenuItem, MenuItemLabel
    from apps.pages.models import StaticPage, StaticPageTranslation

    for model in (MenuItem, MenuItemLabel, StaticPage, StaticPageTranslation):
        post_save.connect(_bump, sender=model, dispatch_uid=f"ccjbump_save_{model.__name__}")
        post_delete.connect(_bump, sender=model, dispatch_uid=f"ccjbump_del_{model.__name__}")
