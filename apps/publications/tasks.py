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

"""Yayın periyodik işleri — açık atıf sayıları (i4OC / OpenCitations).

OpenCitations COCI ücretsizdir ve kimlik doğrulaması istemez; DOI başına
atıf sayısı çekilir ve makale sayfasında "Cited by N" olarak gösterilir.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger("ccjournal.publications")

OPENCITATIONS_URL = "https://opencitations.net/index/coci/api/v1/citation-count/{doi}"
REFRESH_DAYS = 7
BATCH = 40


def _fetch_count(doi: str) -> int | None:
    req = urllib.request.Request(
        OPENCITATIONS_URL.format(doi=doi),
        headers={"User-Agent": "ccjournal-citedby", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if isinstance(data, list) and data:
        return int(data[0].get("count", 0))
    return None


def fetch_cited_by() -> dict:
    """DOI'li yayımlanmış yayınların açık atıf sayısını tazeler (parti başına 40)."""
    from .models import Publication, PublicationStatus

    stale = timezone.now() - timedelta(days=REFRESH_DAYS)
    qs = (Publication.objects
          .filter(status=PublicationStatus.PUBLISHED, doi__isnull=False)
          .filter(Q(cited_by_fetched_at__isnull=True) | Q(cited_by_fetched_at__lt=stale))
          .select_related("doi")[:BATCH])
    updated = errors = 0
    for pub in qs:
        try:
            count = _fetch_count(pub.doi.doi)
        except Exception:
            errors += 1
            logger.warning("cited-by fetch failed for %s", pub.doi.doi, exc_info=True)
            continue
        if count is not None:
            pub.cited_by_count = count
        pub.cited_by_fetched_at = timezone.now()
        pub.save(update_fields=["cited_by_count", "cited_by_fetched_at"])
        updated += 1
    return {"updated": updated, "errors": errors}
