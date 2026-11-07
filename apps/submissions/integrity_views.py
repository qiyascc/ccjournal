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

"""Entegrite paneli — /manage/integrity/<submission_id>/ (editoryal)."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from .models import Submission


def _can(user) -> bool:
    return bool(getattr(user, "is_authenticated", False) and user.is_staff
                and (user.is_superuser or user.has_editorial_access()))


@staff_member_required
def integrity_panel(request, pk):
    if not _can(request.user):
        raise Http404
    sub = get_object_or_404(
        Submission.objects.select_related("current_publication", "submitter"), pk=pk)

    if request.method == "POST":
        from .integrity import run_checks
        run_checks(sub, network=True)
        messages.success(request, "Full integrity checks completed.")
        return redirect("manage_integrity", pk=sub.pk)

    pub = sub.current_publication
    title = (pub.tr_value("title") if pub else "") or f"Submission #{sub.pk}"
    report = sub.integrity_report or {}
    labels = {
        "references": "Reference DOIs (Crossref)",
        "similarity": "Archive similarity",
        "emails": "Email domains",
        "self_citation": "Self-citation",
        "orcid": "Author ORCID coverage",
    }
    checks = [{"key": k, "label": labels.get(k, k), **v}
              for k, v in (report.get("checks") or {}).items()]
    from apps.plugins.hooks import hooks
    plugin_html = hooks.apply_filters(
        "manage.integrity_extra", "", submission=sub, request=request)
    return render(request, "manage/integrity.html", {
        "sub": sub, "stitle": title, "report": report, "checks": checks,
        "plugin_html": plugin_html,
    })
