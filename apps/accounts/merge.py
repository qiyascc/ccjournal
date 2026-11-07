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

"""Hesap birleştirme (OJS "merge users" karşılığı).

Kaynağın tüm ilişkili kayıtları hedefe taşınır; unique-çakışan satırlar
(aynı round'a iki atama gibi) kaynakta bırakılır ve sayılmaz. Kaynak hesap
SİLİNMEZ — pasifleştirilir (tarihsel bütünlük + geri dönüş kolaylığı).
"""
from __future__ import annotations

import logging

from django.db import IntegrityError, transaction

logger = logging.getLogger("ccjournal.accounts")


@transaction.atomic
def merge_users(source, target) -> int:
    """`source` hesabının kayıtlarını `target`'a taşır; taşınan satır sayısını döndürür."""
    from apps.comms.models import Notification
    from apps.review.models import (
        Discussion, DiscussionMessage, EditorialDecision, ReviewAssignment,
        ReviewerProfile, StageAssignment,
    )
    from apps.submissions.models import Submission, SubmissionFile
    from .models import ApiKey, JournalMembership

    moved = 0
    moved += Submission.objects.filter(submitter=source).update(submitter=target)
    moved += SubmissionFile.objects.filter(uploader=source).update(uploader=target)
    moved += EditorialDecision.objects.filter(editor=source).update(editor=target)
    moved += Discussion.objects.filter(created_by=source).update(created_by=target)
    moved += DiscussionMessage.objects.filter(author=source).update(author=target)
    moved += Notification.objects.filter(recipient=source).update(recipient=target)
    moved += ApiKey.objects.filter(user=source).update(user=target)

    try:
        from apps.subscriptions.models import Subscription
        moved += Subscription.objects.filter(user=source).update(user=target)
    except Exception:
        pass

    for a in ReviewAssignment.objects.filter(reviewer=source):
        try:
            with transaction.atomic():
                a.reviewer = target
                a.save(update_fields=["reviewer"])
                moved += 1
        except IntegrityError:
            logger.info("merge: review assignment %s kept on source (duplicate)", a.pk)
    for sa in StageAssignment.objects.filter(user=source):
        try:
            with transaction.atomic():
                sa.user = target
                sa.save(update_fields=["user"])
                moved += 1
        except IntegrityError:
            sa.delete()
    for m in JournalMembership.objects.filter(user=source):
        try:
            with transaction.atomic():
                m.user = target
                m.save()
                moved += 1
        except IntegrityError:
            m.delete()

    src_prof = ReviewerProfile.objects.filter(user=source).first()
    if src_prof:
        if not ReviewerProfile.objects.filter(user=target).exists():
            src_prof.user = target
            src_prof.save(update_fields=["user"])
            moved += 1
        else:
            src_prof.delete()

    source.is_active = False
    source.save(update_fields=["is_active"])
    logger.info("merged user %s into %s (%s records)", source.pk, target.pk, moved)
    return moved
