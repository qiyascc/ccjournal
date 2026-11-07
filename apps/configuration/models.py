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

"""
Yapılandırma ayarı (DB aynası).

config.ini'deki her (section, key) burada bir satıra karşılık gelir. Dosya
birincil/boot kaynağıdır; bu tablo admin düzenlemesi ve çalışma-anı okuma içindir.
"""
from __future__ import annotations

from django.db import models

BOOTSTRAP_SECTIONS = {"general", "database"}
SECRET_KEYS = {("general", "secret_key"), ("email", "password")}


class ConfigSetting(models.Model):
    section = models.CharField(max_length=64)
    key = models.CharField(max_length=64)
    value = models.TextField(blank=True)
    is_secret = models.BooleanField(default=False)

    class Meta:
        unique_together = ("section", "key")
        ordering = ["section", "key"]
        verbose_name = "Configuration"
        verbose_name_plural = "Configuration"

    def __str__(self) -> str:
        return f"[{self.section}] {self.key}"

    @property
    def requires_restart(self) -> bool:
        return self.section in BOOTSTRAP_SECTIONS

    @property
    def masked_value(self) -> str:
        return "••••••" if (self.is_secret and self.value) else self.value
