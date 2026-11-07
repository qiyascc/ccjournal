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

"""Hakem karşılaştırma — /manage/reviews/<submission_id>/ (editoryal).

Bir gönderinin TÜM değerlendirmeleri yan yana: öneri, tarihler, editöre/yazara
yorumlar, özel form yanıtları ve hakem ekleri. Editör kararını tek ekrandan verir.
"""
from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from apps.submissions.models import FileStage, Submission


def _can(user) -> bool:
    return bool(getattr(user, "is_authenticated", False)
                and user.is_staff
                and (user.is_superuser or user.has_editorial_access()))


@staff_member_required
def compare_reviews(request, pk):
    if not _can(request.user):
        raise Http404
    sub = get_object_or_404(
        Submission.objects.select_related("current_publication"), pk=pk)
    pub = sub.current_publication
    title = (pub.tr_value("title") if pub else "") or f"Submission #{sub.pk}"

    attachments = {}
    for f in sub.files.filter(file_stage=FileStage.REVIEW_ATTACHMENT):
        attachments.setdefault(f.uploader_id, []).append(f)

    rounds = []
    for rnd in sub.review_rounds.order_by("round").prefetch_related(
            "assignments__reviewer"):
        cards = []
        for i, a in enumerate(rnd.assignments.order_by("date_assigned"), start=1):
            responses = []
            for row in (a.form_responses or []):
                val = row.get("value", "")
                responses.append({"label": row.get("label", ""),
                                  "value": ", ".join(val) if isinstance(val, list) else val})
            cards.append({
                "n": i, "a": a,
                "reviewer": a.reviewer,
                "status": ("declined" if a.declined
                           else "completed" if a.date_completed
                           else "accepted" if a.date_confirmed else "invited"),
                "responses": responses,
                "attachments": attachments.get(a.reviewer_id, []),
            })
        rounds.append({"round": rnd, "cards": cards})

    from .suggest import suggest_reviewers
    suggestions = suggest_reviewers(sub)
    author_suggested = sub.suggested_reviewers or []
    from apps.plugins.hooks import hooks
    plugin_html = hooks.apply_filters(
        "manage.reviews_extra", "", submission=sub, request=request)
    return render(request, "manage/reviews.html",
                  {"sub": sub, "stitle": title, "rounds": rounds,
                   "suggestions": suggestions,
                   "author_suggested": author_suggested,
                   "plugin_html": plugin_html})
