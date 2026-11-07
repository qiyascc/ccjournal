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

"""İstatistik kayıt/sorgu servisi — COUNTER kurallarına uygun sayım.

COUNTER 5 / OJS davranışı:
  * Robot/bot trafiği sayılmaz (UA filtresi).
  * **Double-click filtering**: aynı ziyaretçinin aynı öğeye 30 sn içindeki
    tekrar istekleri TEK sayılır (sayfa yenileme +1 üretmez). Ziyaretçi kimliği
    oturum anahtarı, yoksa IP+UA hash'idir — COUNTER'ın önerdiği sıra.
  * Ek olarak (OJS'te olmayan iyileştirme): staff (editör/admin) görüntülemeleri
    varsayılan olarak sayılmaz — kendi tıklamaların istatistiği şişirmesin.
    Constance → Display → STATS_COUNT_STAFF_VIEWS ile açılabilir.

Not: double-click penceresi cache üzerinde tutulur. Varsayılan locmem cache
worker-başınadır; birden çok gunicorn worker'ında filtre "çoğunlukla" işler,
paylaşımlı bir cache backend'i kurulursa birebir kesinleşir.
"""
from __future__ import annotations

import hashlib
import re

from django.core.cache import cache
from django.db.models import F, Sum
from django.utils import timezone

from .models import Metric, MetricDay

DOUBLECLICK_WINDOW = 30

_BOT_RE = re.compile(
    r"bot|crawl|spider|slurp|bingpreview|facebookexternalhit|mediapartners|"
    r"curl|wget|python-requests|httpclient|headless|scrapy|monitor|uptime",
    re.I,
)


def is_bot(request) -> bool:
    ua = request.META.get("HTTP_USER_AGENT", "")
    return not ua or bool(_BOT_RE.search(ua))


def _visitor_key(request) -> str:
    """Ziyaretçi kimliği: oturum anahtarı > IP+UA hash (COUNTER sıralaması)."""
    sess = getattr(request, "session", None)
    sk = getattr(sess, "session_key", None)
    if sk:
        return f"s:{sk}"
    ip = (request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
          or request.META.get("REMOTE_ADDR", "?"))
    ua = request.META.get("HTTP_USER_AGENT", "")[:200]
    return "a:" + hashlib.md5(f"{ip}|{ua}".encode()).hexdigest()


class StatsService:
    @staticmethod
    def record(request, submission, metric: str, *, galley=None) -> None:
        if is_bot(request):
            return
        user = getattr(request, "user", None)
        if getattr(user, "is_staff", False):
            try:
                from constance import config
                if not config.STATS_COUNT_STAFF_VIEWS:
                    return
            except Exception:
                return
        dc_key = (f"stats:dc:{_visitor_key(request)}:{submission.pk}:"
                  f"{metric}:{galley.pk if galley else 0}")
        if not cache.add(dc_key, 1, DOUBLECLICK_WINDOW):
            return
        row, created = MetricDay.objects.get_or_create(
            submission=submission, galley=galley, metric=metric,
            date=timezone.localdate(), defaults={"count": 1},
        )
        if not created:
            MetricDay.objects.filter(pk=row.pk).update(count=F("count") + 1)

    @staticmethod
    def totals(submission) -> dict:
        rows = (MetricDay.objects.filter(submission=submission)
                .values("metric").annotate(total=Sum("count")))
        out = {Metric.ABSTRACT_VIEW: 0, Metric.GALLEY_VIEW: 0}
        for r in rows:
            out[r["metric"]] = r["total"]
        return {"abstract_views": out[Metric.ABSTRACT_VIEW],
                "galley_views": out[Metric.GALLEY_VIEW]}
