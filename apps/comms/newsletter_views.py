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

"""Hesapsız bülten — double opt-in aboneliği.

/newsletter/                    e-posta bırakma formu
/newsletter/confirm/<token>/    onay (imzalı, 7 gün)
/newsletter/unsubscribe/<t>/    tek tık ayrılma (süresiz link, her duyuruda)
"""
from __future__ import annotations

from django.contrib import messages
from django.core import signing
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.web.views import _base_ctx, _journal_or_404

from .models import NewsletterSubscriber

CONFIRM_SALT = "newsletter-confirm"
UNSUB_SALT = "newsletter-unsub"
CONFIRM_MAX_AGE = 7 * 86400


def unsubscribe_url(email: str) -> str:
    from .utils import absolute_url
    token = signing.dumps(email, salt=UNSUB_SALT)
    return absolute_url(f"/newsletter/unsubscribe/{token}/")


def newsletter(request):
    journal = _journal_or_404()
    ctx = _base_ctx(request, journal)
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        if "@" not in email or len(email) > 254:
            messages.error(request, "Please enter a valid email address.")
            return redirect("newsletter")
        sub, _created = NewsletterSubscriber.objects.get_or_create(email=email)
        if sub.confirmed_at:
            messages.success(request, "You are already subscribed. Thank you!")
            return redirect("newsletter")
        token = signing.dumps(email, salt=CONFIRM_SALT)
        from .services import NotificationService
        from .utils import absolute_url
        jt = journal.tr()
        NotificationService.notify_raw(
            journal=journal, to=[email], key="newsletter_confirm",
            subject=f"Confirm your subscription — {jt.title if jt else 'Journal'}",
            body=("Please confirm your subscription to new-issue announcements:\n\n"
                  f"{absolute_url(f'/newsletter/confirm/{token}/')}\n\n"
                  "The link is valid for 7 days. If you did not request this, "
                  "simply ignore this email."))
        return render(request, "web/newsletter.html", {**ctx, "sent": email})
    return render(request, "web/newsletter.html", ctx)


def newsletter_confirm(request, token):
    _journal_or_404()
    try:
        email = signing.loads(token, salt=CONFIRM_SALT, max_age=CONFIRM_MAX_AGE)
    except signing.SignatureExpired:
        messages.error(request, "That confirmation link has expired — subscribe again.")
        return redirect("newsletter")
    except signing.BadSignature:
        raise Http404 from None
    sub = NewsletterSubscriber.objects.filter(email=email).first()
    if sub and not sub.confirmed_at:
        sub.confirmed_at = timezone.now()
        sub.save(update_fields=["confirmed_at"])
    messages.success(request, "Subscription confirmed — see you at the next issue!")
    return redirect("web:home")


def newsletter_unsubscribe(request, token):
    try:
        email = signing.loads(token, salt=UNSUB_SALT)
    except signing.BadSignature:
        raise Http404 from None
    NewsletterSubscriber.objects.filter(email=email).delete()
    journal = _journal_or_404()
    ctx = _base_ctx(request, journal)
    return render(request, "web/newsletter.html", {**ctx, "unsubscribed": email})
