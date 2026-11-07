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

"""Unfold admin dashboard — KPI kartları + kurulum sağlığı + editöryal kanban."""
from __future__ import annotations


def environment_callback(request):
    """Üst barda ortam rozeti."""
    from django.conf import settings
    return ["Development", "warning"] if settings.DEBUG else ["Production", "primary"]


def _setup_health():
    """Kurulum sağlığı kontrol listesi — OJS'in dağınık ayar ekranlarına karşı
    tek bakışta "neyin eksik" panosu. Her madde: ok/label/url/hint."""
    from apps.configuration.services import Config
    from apps.journals.models import Issue, Journal
    from apps.submissions.models import Genre

    items = []

    def add(ok, label, url, hint=""):
        items.append({"ok": bool(ok), "label": label, "url": url, "hint": hint})

    j = Journal.current()
    add(j is not None, "Journal configured", "/setup/" if not j else "/admin/journals/journal/",
        "Run the setup wizard" if not j else "")
    if j:
        add(j.sections.exists(), "At least one section",
            "/admin/journals/section/", "Authors need a section to submit into")
        add(Genre.objects.filter(journal=j).exists(), "File types (genres) defined",
            "/admin/submissions/genre/", "e.g. Article Text, Supplementary")
        add(Issue.objects.filter(journal=j).exists(), "First issue created",
            "/admin/journals/issue/", "Articles publish as part of an issue")
        if j.enable_doi:
            add(bool(j.doi_prefix), "DOI prefix set", "/admin/journals/journal/",
                "DOI minting is on but no prefix")
            add(bool(Config.get("crossref", "username", "")),
                "Crossref credentials", "/admin/configuration/configsetting/",
                "Deposits run in dry-run until set")
    smtp = bool(Config.get("email", "host", ""))
    add(smtp, "Email (SMTP) configured", "/admin/configuration/configsetting/",
        "Without SMTP no email leaves the server (password resets, notifications)")
    site_url = (Config.get("general", "site_url", "") or "").strip()
    add(bool(site_url) and "example.org" not in site_url, "Site URL set",
        "/admin/configuration/configsetting/", "Used for links in emails, OAI, sitemaps")

    missing = [i for i in items if not i["ok"]]
    return {"items": items, "missing": len(missing), "total": len(items)}


def _sub_label(s):
    p = s.current_publication
    if p:
        t = p.translations.first()
        if t and t.title:
            return t.title[:60]
    return f"Submission #{s.pk}"


def dashboard_callback(request, context):
    kpi, kanban = [], []
    try:
        from apps.submissions.models import Submission, SubmissionStatus
        from apps.publications.models import Publication, PublicationStatus
        from apps.journals.models import Issue
        from apps.accounts.models import User
        from apps.review.models import ReviewAssignment
        from apps.formbuilder.models import FormSubmission

        kpi = [
            {"title": "Submissions", "metric": Submission.objects.count(), "icon": "inbox"},
            {"title": "Published", "icon": "article",
             "metric": Publication.objects.filter(status=PublicationStatus.PUBLISHED).count()},
            {"title": "Issues", "metric": Issue.objects.count(), "icon": "menu_book"},
            {"title": "Users", "metric": User.objects.count(), "icon": "person"},
            {"title": "Open reviews", "icon": "rate_review",
             "metric": ReviewAssignment.objects.filter(
                 date_completed__isnull=True, declined=False).count()},
            {"title": "Form inbox", "icon": "dynamic_form",
             "metric": FormSubmission.objects.filter(status=1).count()},
        ]

        def col(title, icon, qs, urlbase="/admin/submissions/submission/{}/change/"):
            items = [{"label": _sub_label(s), "url": urlbase.format(s.pk),
                      "meta": s.created_at.strftime("%d %b")} for s in qs[:6]]
            return {"title": title, "icon": icon, "count": qs.count(), "items": items}

        in_review_ids = set(ReviewAssignment.objects.filter(
            date_completed__isnull=True, declined=False
        ).values_list("review_round__submission_id", flat=True))
        base = Submission.objects.select_related("current_publication").order_by("-id")
        kanban = [
            col("Drafts", "edit_note", base.filter(status=SubmissionStatus.INCOMPLETE)),
            col("Queued", "pending", base.filter(status=SubmissionStatus.QUEUED)
                .exclude(pk__in=in_review_ids)),
            col("In review", "rate_review", base.filter(pk__in=in_review_ids)),
            col("Scheduled", "event", base.filter(status=SubmissionStatus.SCHEDULED)),
            col("Published", "check_circle", base.filter(status=SubmissionStatus.PUBLISHED)),
        ]
    except Exception:
        pass
    context["kpi"] = kpi
    context["kanban"] = kanban
    try:
        context["setup_health"] = _setup_health()
        from apps.tasks.models import Job
        context["failed_jobs"] = Job.objects.filter(status=Job.Status.FAILED).count()
    except Exception:
        context["setup_health"] = None
        context["failed_jobs"] = 0
    return context
