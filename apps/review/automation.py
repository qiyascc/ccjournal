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

"""Editoryal kural motoru (lite) — AI'sız, deterministik otomasyonlar.

Constance → Automation sekmesinden ayarlanır:
  * AUTO_REMIND_INVITE_DAYS  — davete N gün yanıt vermeyen hakeme daveti yeniden
    gönder + editörlere bildir (0 = kapalı).
  * AUTO_NOTIFY_ALL_REVIEWS_DONE — turdaki TÜM raporlar gelince editörlere
    "karar bekleniyor" bildirimi (rapor gönderildiği anda tetiklenir).
  * AUTO_STALE_REVIEW_DAYS — N gündür tek onaylı hakemi olmayan gönderiler için
    editörlere uyarı (haftada bir tekrar; 0 = kapalı).

Zamana bağlı kurallar periyodik görevle (editorial_rules, 6 saatte bir) koşar;
worker yoksa web trafiği tetikler (PeriodicPulse).
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger("ccjournal.review")

STALE_RENOTIFY_DAYS = 7


def _editorial_users():

    from apps.accounts.roles import EDITORIAL_ROLE_NAMES
    from apps.accounts.models import User
    return (User.objects.filter(is_active=True,
                                groups__name__in=EDITORIAL_ROLE_NAMES)
            .distinct()) or User.objects.none()


def _notify_editorial(type_: str, title: str, *, body="", url="", journal=None,
                      email=False):
    from apps.comms.services import NotificationService, NotifyService
    users = list(_editorial_users())
    for u in users:
        NotifyService.create(u, type_, title, body=body, url=url, journal=journal)
    if email:
        to = [u.email for u in users if u.email]
        if to:
            NotificationService.notify_raw(journal=journal, to=to, subject=title,
                                           body=body or title, key=type_)
    return len(users)


def on_review_completed(assignment) -> bool:
    """Rapor gönderildiği anda: turdaki tüm aktif atamalar tamamlandıysa bildir."""
    from constance import config
    if not getattr(config, "AUTO_NOTIFY_ALL_REVIEWS_DONE", True):
        return False
    rnd = assignment.review_round
    active = [a for a in rnd.assignments.all() if not a.declined]
    if not active or any(not a.date_completed for a in active):
        return False
    sub = rnd.submission
    pub = sub.current_publication
    title = (pub.tr_value("title") if pub else "") or f"Submission #{sub.pk}"
    _notify_editorial(
        "reviews_complete",
        f"All reviews in — decision needed: {title}",
        body=f"{len(active)} report(s) completed for submission #{sub.pk}.",
        url=f"/manage/reviews/{sub.pk}/", journal=sub.journal, email=True)
    return True


def run_rules() -> dict:
    """Periyodik: davet zaman aşımı hatırlatmaları + bayat gönderi uyarıları."""
    from constance import config
    out = {"invite_reminders": 0, "stale_alerts": 0}
    days = int(getattr(config, "AUTO_REMIND_INVITE_DAYS", 5) or 0)
    if days > 0:
        out["invite_reminders"] = _remind_unanswered_invites(days)
    stale_days = int(getattr(config, "AUTO_STALE_REVIEW_DAYS", 30) or 0)
    if stale_days > 0:
        out["stale_alerts"] = _alert_stale_submissions(stale_days)
    return out


def _remind_unanswered_invites(days: int) -> int:
    from apps.comms.services import MailService, NotifyService
    from apps.comms.utils import absolute_url

    from .models import ReviewAssignment

    cutoff = timezone.now() - timedelta(days=days)
    qs = (ReviewAssignment.objects
          .filter(date_confirmed__isnull=True, declined=False,
                  date_completed__isnull=True, date_assigned__lte=cutoff)
          .select_related("reviewer", "review_round__submission__journal"))
    sent = 0
    for a in qs:
        if a.date_reminded and a.date_reminded >= cutoff:
            continue
        sub = a.review_round.submission
        review_url = f"/review/{a.access_token}/"
        try:
            NotifyService.create(a.reviewer, "invite_reminder",
                                 "Reminder: review invitation awaiting your reply",
                                 journal=sub.journal, url=review_url)
            if a.reviewer.email:
                journal = sub.journal
                supported = journal.supported_locales or [journal.primary_locale]
                pref = getattr(a.reviewer, "preferred_locale", None)
                locale = pref if pref in supported else journal.primary_locale
                MailService.send("review_request", journal=journal, locale=locale,
                                 to=[a.reviewer.email], related=sub,
                                 context={"due": a.date_due, "journal": str(journal),
                                          "review_url": absolute_url(review_url)})
            a.date_reminded = timezone.now()
            a.save(update_fields=["date_reminded"])
            sent += 1
        except Exception:
            logger.exception("invite reminder failed (assignment %s)", a.pk)
    return sent


def _alert_stale_submissions(days: int) -> int:
    from apps.comms.models import Notification
    from apps.submissions.models import Stage, Submission, SubmissionStatus

    from .models import ReviewRound

    cutoff = timezone.now() - timedelta(days=days)
    renotify_cutoff = timezone.now() - timedelta(days=STALE_RENOTIFY_DAYS)
    alerts = 0
    subs = (Submission.objects
            .filter(stage=Stage.REVIEW, status=SubmissionStatus.QUEUED,
                    date_submitted__lte=cutoff)
            .select_related("current_publication"))
    for sub in subs:
        rnd = sub.review_rounds.order_by("-round").first()
        if rnd and rnd.status in (ReviewRound.Status.ACCEPTED,
                                  ReviewRound.Status.DECLINED):
            continue
        confirmed = bool(rnd and rnd.assignments.filter(
            date_confirmed__isnull=False, declined=False).exists())
        if confirmed:
            continue
        if Notification.objects.filter(
                type="stale_submission", url=f"/manage/reviews/{sub.pk}/",
                created_at__gte=renotify_cutoff).exists():
            continue
        pub = sub.current_publication
        title = (pub.tr_value("title") if pub else "") or f"Submission #{sub.pk}"
        _notify_editorial(
            "stale_submission",
            f"No confirmed reviewer for {days}+ days: {title}",
            body=f"Submission #{sub.pk} has been waiting since "
                 f"{sub.date_submitted:%d %b}.",
            url=f"/manage/reviews/{sub.pk}/", journal=sub.journal)
        alerts += 1
    return alerts
