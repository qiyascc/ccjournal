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
Dayanıklı, DB-destekli iş kuyruğu — broker (Redis/Celery) GEREKTİRMEZ.

Tasarım: ağır/başarısız olabilir işler (Crossref deposit, e-posta, PDF, AI çağrısı)
istek thread'ini bloklamasın. `enqueue()` bir Job yazar; `run_worker` komutu (veya
`run_due()`) işleri çeker, çalıştırır, başarısızlıkta üstel backoff ile yeniden
dener ve max deneme sonunda "dead-letter" (FAILED) bırakır. Tümü tek SQLite/Postgres
üzerinde; ek servis yok (projenin "broker'sız" felsefesiyle tutarlı).
"""
from __future__ import annotations

from django.db import models
from django.utils import timezone


class Job(models.Model):
    class Status(models.IntegerChoices):
        QUEUED = 1, "Queued"
        RUNNING = 2, "Running"
        DONE = 3, "Done"
        FAILED = 4, "Failed (dead-letter)"

    queue = models.CharField(max_length=64, default="default", db_index=True)
    func = models.CharField(max_length=255, help_text="Dotted path, e.g. apps.metadata.tasks.deposit")
    args = models.JSONField(default=list, blank=True)
    kwargs = models.JSONField(default=dict, blank=True)

    status = models.IntegerField(choices=Status.choices, default=Status.QUEUED, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    run_after = models.DateTimeField(default=timezone.now, db_index=True,
                                     help_text="Backoff / zamanlama: bu andan önce çalıştırılmaz")

    result = models.JSONField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Job"
        verbose_name_plural = "Jobs (task queue)"
        indexes = [models.Index(fields=["status", "run_after"])]

    def __str__(self) -> str:
        return f"{self.func} #{self.pk} [{self.get_status_display()}]"


class PeriodicRun(models.Model):
    """Periyodik görevlerin son çalışma kaydı (OJS scheduled_tasks karşılığı).

    Görev tanımları kodda durur (apps.tasks.periodic.REGISTRY); bu tablo yalnız
    "en son ne zaman çalıştı"yı tutar. Compare-and-set güncellemesiyle birden çok
    süreç (web worker'ları + run_worker) arasında yarış-güvenlidir.
    """
    name = models.CharField(max_length=64, unique=True)
    last_run = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Periodic run"

    def __str__(self) -> str:
        return f"{self.name} @ {self.last_run or 'never'}"
