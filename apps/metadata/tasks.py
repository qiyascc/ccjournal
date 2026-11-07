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

"""Kuyruğa uygun metadata işleri (worker tarafından çalıştırılır)."""
from __future__ import annotations


def deposit_publications_job(pub_ids: list[int]) -> dict:
    """Verilen yayınları Crossref'e gönderir (arka planda). JSON-uyumlu özet döner.

    Ağ/HTTP hatasında istisna fırlatır → kuyruk üstel backoff ile yeniden dener.
    """
    from apps.publications.models import Publication
    from .crossref import deposit_publications

    pubs = list(Publication.objects.filter(id__in=pub_ids, doi__isnull=False))
    if not pubs:
        return {"ok": False, "submitted": 0, "detail": "No DOImed publications found."}

    result = deposit_publications(pubs)
    if not result.get("ok") and not result.get("dry_run"):
        raise RuntimeError(result.get("detail") or "Crossref deposit failed")
    return {"ok": bool(result.get("ok")), "submitted": result.get("submitted", 0),
            "dry_run": bool(result.get("dry_run")), "detail": result.get("detail", "")}
