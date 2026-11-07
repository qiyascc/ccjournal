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
Kullanıcı paneli (/dashboard/) — OJS'in "Submissions" panosunun okuyucu-tarafı
karşılığı, ama tek sayfada: yazar gönderileri + hakem davetleri + bildirimler.

Yazar buradan: taslağı sürdürür (wizard), aktif gönderisinin token'lı çalışma
alanına gider, kararları/bildirimleri görür. Hakem buradan: bekleyen davetlerini
tek tıkla açar. Editoryal roller için admin/board kısayolları gösterilir.
"""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.review.models import ReviewAssignment
from apps.submissions.models import Submission, SubmissionStatus

from .views import _base_ctx, _journal_or_404


@login_required
def dashboard(request):
    journal = _journal_or_404()
    ctx = _base_ctx(request, journal)

    if request.method == "POST" and request.POST.get("action") == "mark_read":
        request.user.notifications.filter(is_read=False).update(is_read=True)
        return redirect("dashboard")

    subs = (Submission.objects.filter(submitter=request.user)
            .select_related("current_publication")
            .prefetch_related("current_publication__translations")
            .order_by("-created_at"))
    items = []
    for s in subs:
        pub = s.current_publication
        t = pub.tr(ctx["cloc"]) if pub else None
        title = (t.title if t and t.title else f"Submission #{s.pk}")
        if s.status == SubmissionStatus.INCOMPLETE:
            url, action = reverse("submit:files", args=[s.pk]), "continue"
        elif s.status == SubmissionStatus.PUBLISHED:
            url, action = reverse("web:article", args=[s.pk]), "view"
        else:
            url, action = f"/work/{s.author_token}/", "workspace"
        extra = ""
        if s.stage == 3 and s.status not in (SubmissionStatus.INCOMPLETE,
                                             SubmissionStatus.DECLINED):
            rnd = s.review_rounds.order_by("-round").first()
            if rnd:
                active = [a for a in rnd.assignments.all() if not a.declined]
                if active:
                    done = sum(1 for a in active if a.date_completed)
                    extra = f"{done}/{len(active)} reviews"
        items.append({
            "sub": s, "title": title, "url": url, "action": action,
            "stage": s.get_stage_display(), "status": s.get_status_display(),
            "extra": extra,
        })

    assignments = (ReviewAssignment.objects.filter(reviewer=request.user)
                   .select_related("review_round__submission")
                   .order_by("-date_assigned"))
    pending_reviews = [a for a in assignments if not a.date_completed and not a.declined]
    completed_reviews = [a for a in assignments if a.date_completed]

    notifications = list(request.user.notifications.order_by("-created_at")[:15])
    unread_count = request.user.notifications.filter(is_read=False).count()

    ctx.update({
        "items": items,
        "pending_reviews": pending_reviews,
        "completed_review_count": len(completed_reviews),
        "completed_reviews": completed_reviews[:5],
        "notifications": notifications,
        "unread_count": unread_count,
        "is_editorial": request.user.has_editorial_access(journal),
    })
    return render(request, "web/dashboard.html", ctx)
