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

"""Mesajlaşma-native hakemlik: davete "1" yaz → kabul, "2" yaz → ret.

Kanal-bağımsız çekirdek: Telegram botu (Django ORM'e doğrudan bağlı) ve WhatsApp
sidecar webhook'u aynı `handle_reply` fonksiyonunu çağırır. E-postanın geç
okunduğu coğrafyalarda davet yanıt süresini saatlerden saniyelere indirir —
başka dergi sisteminde olmayan bir akış.
"""
from __future__ import annotations

import logging

from django.utils import timezone

logger = logging.getLogger("ccjournal.review")

ACCEPT_WORDS = {"1", "accept", "yes", "kabul", "evet", "qebul", "qəbul", "ok", "✅"}
DECLINE_WORDS = {"2", "decline", "no", "ret", "red", "hayır", "hayir",
                 "imtina", "yox", "❌"}


def pending_invitation(user):
    """Kullanıcının yanıt bekleyen en yeni daveti (davet edildi, cevapsız)."""
    from .models import ReviewAssignment
    return (ReviewAssignment.objects
            .filter(reviewer=user, declined=False,
                    date_confirmed__isnull=True, date_completed__isnull=True)
            .select_related("review_round__submission__journal")
            .order_by("-date_assigned").first())


def handle_reply(user, text: str) -> str | None:
    """Kısa yanıtı işler; kanalın kullanıcıya geri yazacağı metni döndürür.

    "1"/"2" değilse None döner — çağıran kendi yardım/komut akışına devam eder.
    """
    from apps.comms.utils import absolute_url

    word = (text or "").strip().lower().rstrip(".!")
    accept = word in ACCEPT_WORDS
    decline = word in DECLINE_WORDS
    if not (accept or decline):
        return None

    a = pending_invitation(user)
    if a is None:
        return ("You have no review invitations awaiting a reply. "
                "New invitations will arrive here — reply 1 to accept, 2 to decline.")

    sub = a.review_round.submission
    if accept:
        a.date_confirmed = timezone.now()
        a.save(update_fields=["date_confirmed"])
        url = absolute_url(f"/review/{a.access_token}/")
        due = f" Due date: {a.date_due:%d %b %Y}." if a.date_due else ""
        logger.info("quick-accept: user %s assignment %s", user.pk, a.pk)
        return (f"✅ Accepted — thank you! Submission #{sub.pk}.{due}\n"
                f"Review page: {url}")

    from .public_views import _notify_editors
    from .services import ReviewService
    ReviewService.decline_review(a)
    try:
        _notify_editors(a, declined=True)
    except Exception:
        logger.warning("decline notify failed (assignment %s)", a.pk, exc_info=True)
    logger.info("quick-decline: user %s assignment %s", user.pk, a.pk)
    remaining = pending_invitation(user)
    tail = ("\nYou have another pending invitation — reply 1 to accept it, 2 to decline."
            if remaining else "")
    return ("❌ Declined — the editors have been notified. "
            f"Thank you for the quick response.{tail}")
