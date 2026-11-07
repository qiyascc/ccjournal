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

"""Kuyruğa uygun e-posta işleri (serialize-edilebilir argümanlar)."""
from __future__ import annotations


def send_author_action_email(submission_id: int, title: str, kind: str,
                             work_url: str) -> dict:
    """Yazara aşama bildirimi e-postası (kuyruk veya inline)."""
    from apps.submissions.models import Submission
    from .services import MailService

    sub = (Submission.objects.select_related("journal", "submitter")
           .filter(id=submission_id).first())
    if not sub or not sub.submitter or not sub.submitter.email:
        return {"sent": False, "reason": "no recipient"}
    MailService.send("author_action", journal=sub.journal, related=sub,
                     locale=sub.locale, to=[sub.submitter.email],
                     context={"title": title, "kind": kind, "work_url": work_url,
                              "journal": str(sub.journal)})
    return {"sent": True, "submission": submission_id}


def notify_readers_new_issue(issue_id: int) -> dict:
    """Yeni sayı e-postası — opt-in (notify_new_issue) tüm aktif kullanıcılara.

    OJS "Notify readers" karşılığı; sayı yayımlanınca IssueService kuyruğa atar.
    Kişi başına tek tek gönderilir (BCC listesi sızıntısı olmaz); alıcının tercih
    dili derginin desteklediği dillerdeyse o dil kullanılır.
    """
    from apps.accounts.models import User
    from apps.journals.models import Issue
    from .services import MailService
    from .utils import absolute_url

    issue = Issue.objects.select_related("journal").filter(id=issue_id).first()
    if not issue or not issue.is_published:
        return {"sent": 0, "reason": "issue missing or unpublished"}
    journal = issue.journal
    supported = journal.supported_locales or [journal.primary_locale]
    ctx_base = {
        "issue": str(issue), "journal": str(journal),
        "issue_url": absolute_url(f"/issue/{issue.pk}/"),
        "profile_url": absolute_url("/accounts/profile/"),
    }
    toc_lines = []
    for pub in (issue.publications.filter(status=3)
                .prefetch_related("translations", "authors")
                .order_by("section__seq", "seq")):
        t = (pub.translations.filter(locale=pub.primary_locale).first()
             or pub.translations.first())
        if not t:
            continue
        who = ", ".join(f"{a.given_name} {a.family_name}".strip()
                        for a in pub.authors.all()[:4])
        toc_lines.append(f"• {t.title}" + (f" — {who}" if who else ""))
    ctx_base["toc"] = "\n".join(toc_lines)

    sent = 0
    seen: set[str] = set()
    qs = (User.objects.filter(is_active=True, notify_new_issue=True)
          .exclude(email=""))
    for u in qs.iterator():
        seen.add(u.email.lower())
        locale = u.preferred_locale if u.preferred_locale in supported \
            else journal.primary_locale
        ok = MailService.send("issue_published", journal=journal, locale=locale,
                              to=[u.email], related=issue, context=dict(ctx_base))
        sent += int(bool(ok))

    from .models import NewsletterSubscriber
    from .newsletter_views import unsubscribe_url
    for sub_ in (NewsletterSubscriber.objects
                 .filter(confirmed_at__isnull=False).iterator()):
        if sub_.email.lower() in seen:
            continue
        ctx = dict(ctx_base)
        ctx["profile_url"] = unsubscribe_url(sub_.email)
        ok = MailService.send("issue_published", journal=journal,
                              locale=journal.primary_locale, to=[sub_.email],
                              related=issue, context=ctx)
        sent += int(bool(ok))
    return {"sent": sent, "issue": issue_id}


def send_decision_email(submission_id: int, key: str, locale: str,
                        note: str, decision_label: str) -> dict:
    """Gecikmeli (geri alınabilir) karar e-postası — undo penceresinden sonra koşar."""
    from apps.submissions.models import Submission

    from .services import MailService
    from .utils import absolute_url

    sub = (Submission.objects.select_related("journal", "submitter")
           .filter(id=submission_id).first())
    if not sub or not sub.submitter or not sub.submitter.email:
        return {"sent": False, "reason": "no recipient"}
    ok = MailService.send(
        key, journal=sub.journal, locale=locale, to=[sub.submitter.email],
        related=sub,
        context={"decision": decision_label, "note": note,
                 "work_url": absolute_url(f"/work/{sub.author_token}/")})
    return {"sent": bool(ok)}


def send_custom_email(submission_id: int, subject: str, body: str) -> dict:
    """Gecikmeli özel (editör-düzenlemeli) e-posta."""
    from apps.submissions.models import Submission

    from .services import NotificationService

    sub = (Submission.objects.select_related("journal", "submitter")
           .filter(id=submission_id).first())
    if not sub or not sub.submitter or not sub.submitter.email:
        return {"sent": False, "reason": "no recipient"}
    results = NotificationService.notify_raw(
        journal=sub.journal, to=[sub.submitter.email], subject=subject,
        body=body, key="decision_custom", related=sub)
    return {"sent": any(ok for ok, _ in results.values())}
