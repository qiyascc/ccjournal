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
Gerçek-zamanlı editöryal board — İZOLE staff sayfası (6 okuyucu temasına dokunmaz).

Kanban: gönderiler aşamaya göre (Submission/Review/Copyediting/Production), sayaç,
aşamada geçen gün, geciken hakem uyarısı, hakem yükü. "Real-time" = HTMX polling
(broker/websocket yok). Presence = poll-tabanlı (BoardPresence heartbeat). Komut
paleti (⌘K) istemci tarafı (Alpine). Editöryal rollere kapalıdır.
"""
from __future__ import annotations

import json
from datetime import timedelta

from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from apps.submissions.models import Stage, Submission, SubmissionStatus

_STAGES = [
    (Stage.SUBMISSION, "Submission"),
    (Stage.REVIEW, "Review"),
    (Stage.EDITING, "Copyediting"),
    (Stage.PRODUCTION, "Production"),
]
_PRESENCE_WINDOW = 45


def _can(user) -> bool:
    return bool(getattr(user, "is_authenticated", False)
                and (user.is_superuser or user.has_editorial_access()))


def _card(sub, today) -> dict:
    pub = sub.current_publication or sub.publications.first()
    title = (pub.tr_value("title") if pub else "") or "(untitled)"
    latest = None
    for r in sub.review_rounds.all():
        if latest is None or r.round > latest.round:
            latest = r
    assigned = completed = overdue = 0
    if latest:
        for a in latest.assignments.all():
            assigned += 1
            if a.date_completed:
                completed += 1
            elif a.date_due and a.date_due < today and not a.declined:
                overdue += 1
    days = (timezone.now() - sub.date_status_modified).days if sub.date_status_modified else 0
    return {
        "id": sub.id, "title": title,
        "submitter": (sub.submitter.full_name if sub.submitter else ""),
        "days": days, "assigned": assigned, "completed": completed, "overdue": overdue,
        "url": f"/admin/submissions/submission/{sub.id}/change/",
    }


def _columns():
    today = timezone.localdate()
    subs = (Submission.objects
            .exclude(status__in=[SubmissionStatus.PUBLISHED, SubmissionStatus.DECLINED])
            .select_related("current_publication", "submitter")
            .prefetch_related("review_rounds__assignments", "publications__translations"))
    buckets: dict[int, list] = {s: [] for s, _ in _STAGES}
    for sub in subs:
        if sub.stage in buckets:
            buckets[sub.stage].append(_card(sub, today))
    return [{"stage": s, "label": lbl, "cards": buckets[s], "count": len(buckets[s])}
            for s, lbl in _STAGES]


def _present():
    from apps.review.models import BoardPresence
    cutoff = timezone.now() - timedelta(seconds=_PRESENCE_WINDOW)
    return [(p.user.full_name or p.user.email)
            for p in BoardPresence.objects.filter(last_seen__gte=cutoff).select_related("user")]


@ensure_csrf_cookie
def board(request):
    if not _can(request.user):
        return redirect("/accounts/login/?next=/manage/board/")
    columns = _columns()
    cards = [{"id": c["id"], "title": c["title"], "url": c["url"]}
             for col in columns for c in col["cards"]]
    return render(request, "manage/board.html", {
        "columns": columns, "present": _present(),
        "cards_json": json.dumps(cards),
    })


def board_columns(request):
    if not _can(request.user):
        return HttpResponse(status=403)
    return render(request, "manage/_board_columns.html", {"columns": _columns()})


@require_POST
def board_ping(request):
    if not _can(request.user):
        return HttpResponse(status=403)
    from apps.review.models import BoardPresence
    BoardPresence.objects.update_or_create(user=request.user)
    return HttpResponse(status=204)
