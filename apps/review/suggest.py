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

"""Akıllı hakem önerisi — deterministik, AI'sız.

Skor bileşenleri (şeffaf, açıklanabilir):
  +3 ilgi alanı ↔ anahtar kelime kesişimi (her biri)
  +2 uzmanlık metninde anahtar kelime geçişi (her biri, ilk 5)
  +1 tamamlanmış değerlendirme geçmişi (log ölçekli, en çok +3)
  -2 açık (bekleyen) atama başına yük cezası
COI bayrakları: yazarla aynı kurum · hakem bu makalenin yazarı (e-posta) —
ikincisi öneriden tamamen düşürülür. Tatil modundakiler ve yıllık limiti
dolanlar listelenmez.
"""
from __future__ import annotations

import math
import re

from django.utils import timezone


def _terms(publication) -> set[str]:
    out: set[str] = set()
    for k in publication.keywords.all():
        out |= {w for w in re.findall(r"\w{4,}", k.term.lower())}
    t = publication.tr(publication.primary_locale)
    if t:
        out |= {w for w in re.findall(r"\w{5,}", (t.title or "").lower())}
    return out


def suggest_reviewers(submission, limit: int = 8) -> list[dict]:
    from .models import ReviewerProfile

    pub = submission.current_publication
    if not pub:
        return []
    terms = _terms(pub)
    author_emails = {a.email.lower() for a in pub.authors.all() if a.email}
    author_affils = [a.affiliation.lower() for a in pub.authors.all() if a.affiliation]
    today = timezone.localdate()
    year = today.year

    already = set(
        submission.review_rounds.values_list("assignments__reviewer_id", flat=True))

    out = []
    qs = (ReviewerProfile.objects.filter(is_available=True)
          .select_related("user")
          .prefetch_related("interests", "user__review_assignments"))
    for prof in qs:
        u = prof.user
        if u.pk in already or not u.is_active:
            continue
        if u.email.lower() in author_emails:
            continue
        if prof.unavailable_until and prof.unavailable_until >= today:
            continue
        assignments = list(u.review_assignments.all())
        this_year = sum(1 for a in assignments
                        if a.date_confirmed and a.date_confirmed.year == year
                        and not a.declined)
        if prof.max_per_year and this_year >= prof.max_per_year:
            continue

        interest_words = set()
        for i in prof.interests.all():
            interest_words |= {w for w in re.findall(r"\w{4,}", i.name.lower())}
        overlap = len(terms & interest_words)
        expertise_hits = sum(1 for w in list(terms)[:40]
                             if w in (prof.expertise or "").lower())
        completed = sum(1 for a in assignments if a.date_completed)
        pending = sum(1 for a in assignments
                      if not a.date_completed and not a.declined)
        score = (3 * overlap + 2 * min(expertise_hits, 5)
                 + min(3, math.floor(math.log1p(completed) * 1.5)) - 2 * pending)
        if score <= 0 and not overlap:
            continue

        coi = []
        raff = (prof.affiliation or "").lower()
        if raff and any(raff in a or a in raff for a in author_affils if a):
            coi.append("same affiliation as an author")
        out.append({"profile": prof, "user": u, "score": score,
                    "overlap": overlap, "completed": completed,
                    "pending": pending, "coi": coi})
    out.sort(key=lambda r: (-r["score"], r["pending"], -r["completed"]))
    return out[:limit]
