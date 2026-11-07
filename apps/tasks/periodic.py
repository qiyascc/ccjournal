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
Broker'sız periyodik görevler (OJS'in Acron eklentisinin karşılığı, çekirdekte).

İki tetikleyici, aynı kayıt üzerinden yarış-güvenli:
  * `run_worker` döngüsü her turda `maybe_run_periodic()` çağırır (varsa).
  * Worker YOKSA bile web istekleri tetikler: PeriodicPulseMiddleware her
    istekte (süreç başına ~60 sn'de bir) kontrol eder ve zamanı gelen görevi
    arka-plan thread'inde çalıştırır — istek asla bloklanmaz, cron gerekmez.

Görev eklemek: REGISTRY'ye (ad, "modül.fonksiyon", saniye) satırı ekle.
Fonksiyon argümansız çağrılır ve JSON-serialize edilebilir bir özet döndürmelidir.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger("ccjournal.tasks")

REGISTRY: list[tuple[str, str, int]] = [
    ("review_reminders", "apps.review.tasks.send_due_reminders", 6 * 3600),
    ("cited_by", "apps.publications.tasks.fetch_cited_by", 24 * 3600),
    ("editorial_rules", "apps.review.automation.run_rules", 6 * 3600),
]


def maybe_run_periodic(*, force: bool = False) -> list[str]:
    """Zamanı gelen periyodik görevleri çalıştırır; çalışanların adlarını döndürür.

    Compare-and-set (`filter(last_run=old).update(last_run=now)`) sayesinde aynı
    görevi aynı anda yalnız bir süreç kazanır.
    """
    from .models import PeriodicRun
    from .queue import _import

    ran: list[str] = []
    now = timezone.now()
    for name, path, every in REGISTRY:
        row, _ = PeriodicRun.objects.get_or_create(name=name)
        due = force or row.last_run is None or (now - row.last_run) >= timedelta(seconds=every)
        if not due:
            continue
        claimed = (PeriodicRun.objects
                   .filter(pk=row.pk, last_run=row.last_run)
                   .update(last_run=now))
        if not claimed:
            continue
        try:
            result = _import(path)()
            logger.info("periodic %s ran: %s", name, result)
            ran.append(name)
        except Exception:
            logger.exception("periodic %s failed", name)
    return ran
