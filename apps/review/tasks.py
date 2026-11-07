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

"""Değerlendirme periyodik işleri — otomatik hakem hatırlatmaları.

OJS'te "review reminder" zamanlanmış görevi cron/Acron ister; burada
apps.tasks.periodic REGISTRY üzerinden broker'sız çalışır.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger("ccjournal.review")

REMIND_BEFORE_DAYS = 3
RESEND_EVERY_DAYS = 3


def send_due_reminders() -> dict:
    """Yaklaşan/geciken değerlendirmeler için hakeme e-posta + in-app bildirim.

    Tekrarı `date_reminded` önler (en erken RESEND_EVERY_DAYS'te bir).
    Dönüş: {"sent": n} — periodic log'una düşer.
    """
    from apps.comms.services import MailService, NotifyService
    from apps.comms.utils import absolute_url
    from .models import ReviewAssignment

    today = timezone.localdate()
    now = timezone.now()
    horizon = today + timedelta(days=REMIND_BEFORE_DAYS)

    qs = (ReviewAssignment.objects
          .filter(date_completed__isnull=True, declined=False,
                  date_due__isnull=False, date_due__lte=horizon)
          .select_related("reviewer", "review_round__submission__journal"))

    sent = 0
    for a in qs:
        if a.date_reminded and (now - a.date_reminded) < timedelta(days=RESEND_EVERY_DAYS):
            continue
        reviewer = a.reviewer
        sub = a.review_round.submission
        overdue = a.date_due < today
        review_url = f"/review/{a.access_token}/"
        title = ("Review overdue" if overdue else "Review due soon")
        try:
            NotifyService.create(reviewer, "review_reminder", title,
                                 body=f"Due {a.date_due}", journal=sub.journal,
                                 url=review_url)
            if reviewer.email:
                supported = sub.journal.supported_locales or [sub.journal.primary_locale]
                pref = getattr(reviewer, "preferred_locale", None)
                locale = pref if pref in supported else sub.journal.primary_locale
                MailService.send(
                    "review_reminder", journal=sub.journal, locale=locale,
                    to=[reviewer.email], related=sub,
                    context={"due": a.date_due, "overdue": overdue,
                             "journal": str(sub.journal),
                             "review_url": absolute_url(review_url)})
            a.date_reminded = now
            a.save(update_fields=["date_reminded"])
            sent += 1
        except Exception:
            logger.exception("review reminder failed (assignment %s)", a.pk)
    return {"sent": sent, "checked": qs.count()}
