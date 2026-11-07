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

"""Kurulu temalar. Tema = veri (manifest + CSS); kod çalıştırmaz (plugin'den güvenli)."""
from __future__ import annotations

from django.db import models


class InstalledTheme(models.Model):
    key = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    version = models.CharField(max_length=24, default="1.0.0")
    author = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]
        verbose_name = "Theme"

    def __str__(self) -> str:
        return f"{self.name} ({self.key})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_active:
            InstalledTheme.objects.exclude(pk=self.pk).filter(is_active=True).update(is_active=False)
        from .loaders import invalidate
        invalidate()
