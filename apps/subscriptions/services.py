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

"""Erişim kontrolü — paywall yalnızca waffle 'subscriptions' anahtarı aktifken uygulanır."""
from __future__ import annotations

from django.utils import timezone


class SubscriptionService:
    SWITCH = "subscriptions"

    @staticmethod
    def enabled() -> bool:
        try:
            from waffle import switch_is_active
            return bool(switch_is_active(SubscriptionService.SWITCH))
        except Exception:
            return False

    @staticmethod
    def has_active(user, journal) -> bool:
        if not user or not getattr(user, "is_authenticated", False):
            return False
        from .models import Subscription
        today = timezone.localdate()
        return Subscription.objects.filter(
            journal=journal, user=user, status=Subscription.Status.ACTIVE,
            date_end__gte=today).exists()

    @staticmethod
    def has_access(user, issue) -> bool:
        """Galley indirme erişimi. Anahtar kapalıysa veya açık erişimse herkes erişir."""
        if not SubscriptionService.enabled():
            return True
        if issue is None:
            return True
        from apps.journals.models import Issue
        if issue.access == Issue.Access.OPEN:
            return True
        if issue.open_access_date and issue.open_access_date <= timezone.localdate():
            return True
        if getattr(user, "is_staff", False):
            return True
        return SubscriptionService.has_active(user, issue.journal)
