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

"""İş kuyruğu mantığı: enqueue + claim + çalıştır + retry/backoff + dead-letter."""
from __future__ import annotations

import importlib
import json
import logging
import traceback
from datetime import timedelta

from django.utils import timezone

from .models import Job

logger = logging.getLogger("ccjournal.tasks")

MAX_BACKOFF = 3600


def enqueue(func, *args, run_after=None, max_attempts: int = 3,
            queue: str = "default", **kwargs) -> Job:
    """Bir işi kuyruğa yazar. `func` bir callable veya 'modül.fonksiyon' yoludur."""
    path = func if isinstance(func, str) else f"{func.__module__}.{func.__qualname__}"
    return Job.objects.create(
        func=path, args=list(args), kwargs=kwargs, max_attempts=max_attempts,
        queue=queue, run_after=run_after or timezone.now(),
    )


def enqueue_or_run(func, *args, **kwargs):
    """EAGER modda (settings.TASKS_ALWAYS_EAGER, varsayılan True) işi HEMEN inline
    çalıştırır — worker gerekmez, davranış eskisiyle aynı. Worker'lı kurulumda
    (`always_eager=false`) işi kuyruğa atar (bloklamaz).

    NOT: kuyruk modunda `args`/`kwargs` JSON-serialize edilebilir olmalıdır
    (model örneği değil, id geç). eager modda her tür argüman çalışır.
    """
    from django.conf import settings
    if getattr(settings, "TASKS_ALWAYS_EAGER", True):
        fn = func if callable(func) else _import(func)
        return fn(*args, **kwargs)
    return enqueue(func, *args, **kwargs)


def _import(path: str):
    mod, name = path.rsplit(".", 1)
    return getattr(importlib.import_module(mod), name)


def _jsonable(value) -> bool:
    try:
        json.dumps(value)
        return True
    except (TypeError, ValueError):
        return False


def _claim(job: Job) -> bool:
    """Yarış-güvenli sahiplenme: yalnız hâlâ QUEUED ise RUNNING'e çeker (tek worker kazanır)."""
    n = (Job.objects.filter(pk=job.pk, status=Job.Status.QUEUED)
         .update(status=Job.Status.RUNNING, started_at=timezone.now()))
    return n == 1


def run_job(job: Job) -> bool:
    """Tek işi çalıştırır. Başarı → True. Hata → retry (backoff) veya dead-letter."""
    if not _claim(job):
        return False
    job.attempts += 1
    try:
        result = _import(job.func)(*job.args, **job.kwargs)
        job.status = Job.Status.DONE
        job.result = result if _jsonable(result) else str(result)
        job.last_error = ""
        job.finished_at = timezone.now()
        job.save(update_fields=["attempts", "status", "result", "last_error", "finished_at"])
        logger.info("job %s done: %s", job.pk, job.func)
        return True
    except Exception as exc:  # noqa: BLE001 — kuyruk her hatayı yakalar (retry/dead-letter)
        job.last_error = traceback.format_exc()[-4000:]
        if job.attempts < job.max_attempts:
            backoff = min(60 * (2 ** (job.attempts - 1)), MAX_BACKOFF)
            job.status = Job.Status.QUEUED
            job.run_after = timezone.now() + timedelta(seconds=backoff)
            job.started_at = None
            job.save(update_fields=["attempts", "status", "run_after", "started_at", "last_error"])
            logger.warning("job %s failed (attempt %s/%s), retry in %ss: %s",
                           job.pk, job.attempts, job.max_attempts, backoff, exc)
        else:
            job.status = Job.Status.FAILED
            job.finished_at = timezone.now()
            job.save(update_fields=["attempts", "status", "finished_at", "last_error"])
            logger.error("job %s dead-lettered after %s attempts: %s",
                         job.pk, job.attempts, exc)
        return False


def run_due(limit: int = 20) -> int:
    """Vadesi gelmiş QUEUED işleri çalıştırır. Başarılı iş sayısını döndürür."""
    now = timezone.now()
    jobs = list(Job.objects.filter(status=Job.Status.QUEUED, run_after__lte=now)
                .order_by("run_after")[:limit])
    return sum(1 for job in jobs if run_job(job))
