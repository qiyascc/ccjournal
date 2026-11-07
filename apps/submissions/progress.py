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

"""Yazar için "kargo takibi" verisi.

Belirsizlik, yazarların bir numaralı şikâyeti: "makalem nerede, ne kadar sürer?"
Bu servis mevcut kayıtlardan (karar geçmişi, turlar, tarihler) bir zaman çizelgesi
ve dergi genelinde DÜRÜST bir medyan ilk-karar süresi üretir; /work/<token>/ ve
panelde gösterilir. Hiçbir tahmin uydurulmaz — yalnız gerçekleşen veriler.
"""
from __future__ import annotations

from django.utils import timezone

from .models import Stage, Submission, SubmissionStatus

STEP_KEYS = ["submitted", "review", "copyediting", "production", "published"]
STEP_LABELS = {
    "submitted": "Submitted",
    "review": "In review",
    "copyediting": "Copyediting",
    "production": "Production",
    "published": "Published",
}


def _current_index(sub) -> int:
    if sub.status == SubmissionStatus.PUBLISHED:
        return 4
    return {Stage.SUBMISSION: 0, Stage.REVIEW: 1,
            Stage.EDITING: 2, Stage.PRODUCTION: 3}.get(sub.stage, 0)


def median_first_decision_days(journal, sample: int = 100) -> int | None:
    """Dergide gönderimden İLK editoryal karara medyan gün (son `sample` gönderi)."""
    from apps.review.models import EditorialDecision

    rows = (EditorialDecision.objects
            .filter(submission__journal=journal,
                    submission__date_submitted__isnull=False)
            .order_by("submission_id", "created_at")
            .values_list("submission_id", "created_at",
                         "submission__date_submitted"))
    firsts: dict[int, int] = {}
    for sid, decided, submitted in rows:
        if sid in firsts:
            continue
        days = (decided - submitted).days
        if days >= 0:
            firsts[sid] = days
    values = sorted(firsts.values())[-sample:]
    if not values:
        return None
    values.sort()
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) // 2


def timeline(submission: Submission) -> dict:
    """Şablon için ilerleme verisi: adımlar, aktif adım, hakem sayacı, süreler."""
    from apps.review.models import EditorialDecision

    idx = _current_index(submission)
    declined = submission.status == SubmissionStatus.DECLINED

    decisions = list(submission.decisions.order_by("created_at")
                     .values_list("decision", "created_at"))
    D = EditorialDecision.Decision
    review_started = next((c for d, c in decisions if d == D.SEND_TO_REVIEW), None)
    accepted_at = next((c for d, c in decisions if d == D.ACCEPT), None)

    dates = {
        "submitted": submission.date_submitted,
        "review": review_started,
        "copyediting": accepted_at,
        "production": next((c for d, c in decisions if d == D.SEND_TO_PRODUCTION), None),
        "published": None,
    }
    pub = submission.current_publication
    if pub and pub.date_published:
        dates["published"] = pub.date_published

    steps = []
    for i, key in enumerate(STEP_KEYS):
        steps.append({
            "key": key, "label": STEP_LABELS[key],
            "state": ("done" if i < idx or (i == 4 and idx == 4)
                      else "current" if i == idx else "todo"),
            "date": dates.get(key),
        })

    reviews_total = reviews_done = 0
    overdue = False
    rnd = submission.review_rounds.order_by("-round").first()
    if rnd:
        active = [a for a in rnd.assignments.all() if not a.declined]
        reviews_total = len(active)
        reviews_done = sum(1 for a in active if a.date_completed)
        today = timezone.localdate()
        overdue = any(a.date_due and a.date_due < today and not a.date_completed
                      for a in active)

    anchor = decisions[-1][1] if decisions else submission.date_submitted
    days_in_stage = (timezone.now() - anchor).days if anchor else None

    return {
        "steps": steps,
        "current_index": idx,
        "declined": declined,
        "reviews_total": reviews_total,
        "reviews_done": reviews_done,
        "reviews_overdue": overdue,
        "days_in_stage": days_in_stage,
        "median_first_decision": median_first_decision_days(submission.journal),
    }
