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
Kullanım istatistikleri — COUNTER mantığına yakın, günlük toplanmış sayaçlar.

Her olay için ayrı satır tutmak SQLite'ta şişer; bunun yerine (submission, galley,
metric, gün) bazında tek satırda count artırıyoruz. Bot trafiği basit UA filtresiyle
elenir (COUNTER, robotların sayılmamasını şart koşar).
"""
from __future__ import annotations

from django.db import models


class Metric(models.TextChoices):
    ABSTRACT_VIEW = "abstract", "Abstract view"
    GALLEY_VIEW = "galley", "Galley view / download"


class MetricDay(models.Model):
    submission = models.ForeignKey(
        "submissions.Submission", on_delete=models.CASCADE, related_name="metrics"
    )
    galley = models.ForeignKey(
        "publications.Galley", null=True, blank=True, on_delete=models.SET_NULL
    )
    metric = models.CharField(max_length=16, choices=Metric.choices)
    date = models.DateField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("submission", "galley", "metric", "date")
        indexes = [models.Index(fields=["submission", "metric"])]
        verbose_name = "Metric (daily)"
        verbose_name_plural = "Metrics (daily)"

    def __str__(self) -> str:
        return f"{self.submission_id} · {self.metric} · {self.date}: {self.count}"
