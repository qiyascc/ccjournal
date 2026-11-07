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
Sinyal alıcıları: iş-akışı olaylarını bildirim + e-postaya bağlar.
AppConfig.ready() içinde import edilerek aktive olur.
"""
from __future__ import annotations

from django.dispatch import receiver

from apps.accounts.models import User
from apps.accounts.roles import EDITORIAL_ROLE_NAMES
from .services import (
    MailService, NotifyService,
    decision_recorded, publication_published, review_assigned, submission_created,
)


def _journal_locale(journal, user=None) -> str:
    """
    E-posta dili: VARSAYILAN derginin primary_locale'i. Alıcının tercih ettiği dil
    dergi tarafından destekleniyorsa o kullanılır (aksi halde primary). MailService
    ayrıca şablon yoksa 'en'e düşer.
    """
    primary = journal.primary_locale
    supported = journal.supported_locales or [primary]
    pref = getattr(user, "preferred_locale", None) if user else None
    return pref if pref in supported else primary


def _author_email_and_locale(submission):
    user = submission.submitter
    emails = [user.email] if user and user.email else []
    return emails, _journal_locale(submission.journal, user)


@receiver(submission_created)
def on_submission_created(sender, submission, **kwargs):
    journal = submission.journal
    pub = submission.current_publication
    title = pub.tr_value("title") if pub else f"#{submission.id}"
    to, locale = _author_email_and_locale(submission)

    try:
        from django.conf import settings as dj_settings

        from apps.tasks.queue import enqueue_or_run
        eager = getattr(dj_settings, "TASKS_ALWAYS_EAGER", True)
        enqueue_or_run("apps.submissions.integrity.run_checks_job",
                       submission.id, network=not eager)
    except Exception:
        import logging
        logging.getLogger("ccjournal.integrity").warning(
            "integrity check scheduling failed (submission %s)", submission.pk,
            exc_info=True)

    if submission.submitter:
        NotifyService.create(submission.submitter, "submission_ack",
                             "Submission received", body=title, journal=journal,
                             url=f"/submit/{submission.id}/done/")
    MailService.send("submission_ack", journal=journal, locale=locale, to=to, related=submission,
                     context={"title": title, "journal": str(journal)})

    _notify_coauthors(submission)

    editors = User.objects.filter(
        groups__name__in=EDITORIAL_ROLE_NAMES, is_active=True).distinct()
    for u in editors:
        NotifyService.create(u, "new_submission", "New submission",
                             body=title, journal=journal,
                             url=f"/admin/submissions/submission/{submission.id}/change/")
        if u.email:
            MailService.send("editor_new_submission", journal=journal, related=submission,
                             locale=_journal_locale(journal, u), to=[u.email],
                             context={"title": title, "journal": str(journal)})


@receiver(review_assigned)
def on_review_assigned(sender, assignment, **kwargs):
    from .utils import absolute_url
    reviewer = assignment.reviewer
    submission = assignment.review_round.submission
    review_url = f"/review/{assignment.access_token}/"
    NotifyService.create(reviewer, "review_request", "Review request",
                         journal=submission.journal,
                         url=review_url)
    if reviewer.email:
        MailService.send("review_request", journal=submission.journal, related=submission,
                         locale=_journal_locale(submission.journal, reviewer), to=[reviewer.email],
                         context={"due": assignment.date_due, "journal": str(submission.journal),
                                  "review_url": absolute_url(review_url)})


@receiver(decision_recorded)
def on_decision_recorded(sender, decision, notify_author=True, **kwargs):
    from apps.review.models import EditorialDecision
    submission = decision.submission
    to, locale = _author_email_and_locale(submission)
    key_map = {
        EditorialDecision.Decision.ACCEPT: "decision_accept",
        EditorialDecision.Decision.DECLINE: "decision_decline",
        EditorialDecision.Decision.INITIAL_DECLINE: "decision_decline",
        EditorialDecision.Decision.PENDING_REVISIONS: "decision_revisions",
    }
    key = key_map.get(decision.decision)
    if not key or not submission.submitter:
        return
    from .utils import absolute_url
    NotifyService.create(submission.submitter, key, decision.get_decision_display(),
                         body=decision.note, journal=submission.journal)
    if not notify_author:
        return
    from constance import config as _cfg
    undo_min = int(getattr(_cfg, "EMAIL_UNDO_MINUTES", 0) or 0)
    if undo_min > 0:
        from datetime import timedelta

        from django.utils import timezone as _tz

        from apps.tasks.queue import enqueue
        enqueue("apps.comms.tasks.send_decision_email",
                submission.id, key, locale, decision.note,
                decision.get_decision_display(),
                run_after=_tz.now() + timedelta(minutes=undo_min))
        return
    work_url = absolute_url(f"/work/{submission.author_token}/")
    MailService.send(key, journal=submission.journal, locale=locale, to=to, related=submission,
                     context={"decision": decision.get_decision_display(), "note": decision.note,
                              "work_url": work_url})


@receiver(publication_published)
def on_publication_published(sender, publication, **kwargs):
    submission = publication.submission
    try:
        from apps.accounts.orcid_push import push_enabled
        if push_enabled():
            from apps.tasks.queue import enqueue_or_run
            enqueue_or_run("apps.accounts.orcid_push.push_publication", publication.id)
    except Exception:
        import logging
        logging.getLogger("ccjournal.accounts").warning(
            "ORCID push scheduling failed (publication %s)", publication.pk,
            exc_info=True)
    if not submission.submitter:
        return
    title = publication.tr_value("title")
    to, locale = _author_email_and_locale(submission)
    NotifyService.create(submission.submitter, "published", "Your article is published",
                         body=title, journal=submission.journal)
    MailService.send("publication_published", journal=submission.journal, locale=locale, related=submission,
                     to=to, context={"title": title, "journal": str(submission.journal)})


def _notify_coauthors(submission):
    """Ortak yazarlara görünürlük: workspace + kişisel CRediT onay linki."""
    from .services import NotificationService
    from .utils import absolute_url
    pub = submission.current_publication
    if not pub:
        return
    submitter_email = (submission.submitter.email.lower()
                       if submission.submitter and submission.submitter.email else "")
    t = pub.tr(pub.primary_locale)
    title = (t.title if t else f"Submission #{submission.pk}")
    for a in pub.authors.all():
        if not a.email or a.email.lower() == submitter_email:
            continue
        try:
            NotificationService.notify_raw(
                journal=submission.journal, to=[a.email],
                key="coauthor_notice",
                subject=f"You are listed as a co-author: {title}",
                body=(f"Dear {a.given_name},\n\n"
                      f"You are listed as a co-author of \"{title}\", just "
                      "submitted to the journal. You can follow its progress here:\n"
                      f"{absolute_url(f'/work/{submission.author_token}/')}\n\n"
                      "Please confirm your contribution (CRediT) here:\n"
                      f"{absolute_url(f'/work/{submission.author_token}/credit/{a.access_token}/')}\n\n"
                      "If you are not an author of this work, reply to this email."),
                related=submission)
        except Exception:
            import logging
            logging.getLogger("ccjournal.comms").warning(
                "coauthor notice failed (submission %s, author %s)",
                submission.pk, a.pk, exc_info=True)
