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

"""Mini tema editörü — /manage/theme/ (Site Admin/Developer/Designer).

Tema DOSYALARINA dokunmadan CSS değişkenlerini (vurgu rengi, kağıt/mürekkep
tonları, gövde fontu) Journal.settings["theme_vars"] üzerinden ezer; /theme.css
sonuna :root bloğu eklenir, reader cache sürümü zıplatılır. "Reset" temizler.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import redirect, render

VAR_FIELDS = [
    ("accent", "Accent color", "color"),
    ("accent-ink", "Text on accent", "color"),
    ("paper", "Page background", "color"),
    ("paper-2", "Panel background", "color"),
    ("ink", "Body text", "color"),
    ("ink-soft", "Muted text", "color"),
    ("rule", "Hairline/border", "color"),
]

_ALLOWED_ROLES = {"Site Administrator", "Developer", "Designer"}


def _can(user) -> bool:
    return bool(getattr(user, "is_authenticated", False) and user.is_staff
                and (user.is_superuser or (user.role_names & _ALLOWED_ROLES)))


def theme_overrides_css(journal) -> str:
    """Journal.settings.theme_vars → :root override bloğu ('' = yok)."""
    vars_ = ((journal.settings or {}).get("theme_vars") or {}) if journal else {}
    clean = {k: v for k, v in vars_.items()
             if isinstance(v, str) and v.startswith("#") and len(v) in (4, 7)}
    if not clean:
        return ""
    body = ";".join(f"--{k}:{v}" for k, v in clean.items())
    return f"\n/* admin theme overrides */\n:root{{{body}}}\n"


@staff_member_required
def theme_editor(request):
    if not _can(request.user):
        raise Http404
    from apps.core.models import SiteState
    from apps.journals.models import Journal
    journal = Journal.current()
    if journal is None:
        raise Http404
    current = (journal.settings or {}).get("theme_vars") or {}

    if request.method == "POST":
        if request.POST.get("action") == "reset":
            journal.settings = {k: v for k, v in (journal.settings or {}).items()
                                if k != "theme_vars"}
            journal.save(update_fields=["settings"])
            SiteState.bump()
            messages.success(request, "Theme overrides cleared — back to the "
                                      "theme's own palette.")
            return redirect("theme_editor")
        vars_ = {}
        for key, _label, _kind in VAR_FIELDS:
            val = (request.POST.get(key) or "").strip()
            if val.startswith("#") and len(val) in (4, 7):
                vars_[key] = val
        settings_ = dict(journal.settings or {})
        settings_["theme_vars"] = vars_
        journal.settings = settings_
        journal.save(update_fields=["settings"])
        SiteState.bump()
        messages.success(request, "Theme colors saved — refresh the public site "
                                  "to see them.")
        return redirect("theme_editor")

    fields = [{"key": k, "label": lbl, "kind": kind, "value": current.get(k, "")}
              for k, lbl, kind in VAR_FIELDS]
    return render(request, "manage/theme_editor.html",
                  {"fields": fields, "has_overrides": bool(current)})
