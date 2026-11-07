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

"""Tekil site durumu — reader cache invalidation için içerik sürüm damgası.

DB'de paylaşıldığından çok-worker'da tutarlıdır: içerik değişince `bump()` sürümü
artırır; cache anahtarları sürümü içerdiği için eski girdiler otomatik terk edilir
(bayat içerik riski yok). `version()` tek satırlık PK sorgusudur (ucuz)."""
from __future__ import annotations

from django.db import models


class SiteState(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    content_version = models.PositiveBigIntegerField(default=1)

    class Meta:
        verbose_name = "Site state"

    def __str__(self) -> str:
        return f"content_version={self.content_version}"

    @classmethod
    def version(cls) -> int:
        v = cls.objects.filter(pk=1).values_list("content_version", flat=True).first()
        return v if v is not None else 1

    @classmethod
    def bump(cls) -> int:
        cls.objects.get_or_create(pk=1)
        cls.objects.filter(pk=1).update(content_version=models.F("content_version") + 1)
        return cls.version()
