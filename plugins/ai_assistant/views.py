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

"""AI asistan uçları — editoryal yetki ister; plugin kapalıyken 404."""
from __future__ import annotations

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from . import service


def _can(user) -> bool:
    return bool(getattr(user, "is_authenticated", False) and user.is_staff
                and (user.is_superuser or user.has_editorial_access()))


def _guard(request, kind=None):
    if not service.active() or not _can(request.user):
        raise Http404
    if kind is not None and kind not in service.KINDS:
        raise Http404


def _back(request, sub):
    fallback = f"/manage/integrity/{sub.pk}/"
    ref = request.META.get("HTTP_REFERER") or ""
    return redirect(ref if ref.startswith(("http", "/")) and "/manage/" in ref
                    else fallback)


@require_POST
def run(request, kind, pk):
    _guard(request, kind)
    from apps.submissions.models import Submission
    sub = get_object_or_404(Submission, pk=pk)
    service.request_run(kind, sub)
    messages.success(
        request,
        f"{service.KIND_LABELS[kind]} queued — refresh this page in a moment.")
    return _back(request, sub)


@require_POST
def apply_metadata(request, pk):
    _guard(request)
    from apps.submissions.models import Submission
    sub = get_object_or_404(
        Submission.objects.select_related("current_publication"), pk=pk)
    fields = {f for f in ("title", "abstract", "keywords") if request.POST.get(f)}
    changed = service.apply_metadata(sub, fields)
    if changed:
        messages.success(request, "Applied AI suggestions: " + ", ".join(changed))
    else:
        messages.warning(request, "Nothing selected or nothing to apply.")
    return _back(request, sub)
