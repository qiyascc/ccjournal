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
Metadata / dışa aktarım katmanı.

Tombstone: yayımlanmış bir makale içindekilerden çıkarıldığında veya silindiğinde,
OAI-PMH'in "deleted record" mekanizması için metadata izi bırakırız. (OJS:
submission_tombstones).
"""
from __future__ import annotations

from django.db import models


class Tombstone(models.Model):
    journal = models.ForeignKey(
        "journals.Journal", on_delete=models.CASCADE, related_name="tombstones"
    )
    submission = models.ForeignKey(
        "submissions.Submission", null=True, on_delete=models.SET_NULL, related_name="tombstones"
    )
    oai_identifier = models.CharField(max_length=255, db_index=True)
    set_spec = models.CharField(max_length=255, blank=True)
    set_name = models.CharField(max_length=255, blank=True)
    title_snapshot = models.CharField(max_length=512, blank=True)
    doi_snapshot = models.CharField(max_length=255, blank=True)
    date_deleted = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Tombstone"
        verbose_name_plural = "Tombstones"
        ordering = ["-date_deleted"]

    def __str__(self) -> str:
        return self.oai_identifier
