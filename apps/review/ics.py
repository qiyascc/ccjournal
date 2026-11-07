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

"""Editoryal takvim (webcal) — hakem son tarihleri telefon takviminde.

İmzalı, kişiye özel URL: /manage/calendar/<token>/editorial.ics — oturum
gerektirmez (takvim uygulamaları çerez taşımaz), token kullanıcıya bağlıdır ve
kullanıcı editoryal yetkisini yitirirse çalışmaz.
"""
from __future__ import annotations

from django.core import signing
from django.http import Http404, HttpResponse

SALT = "editorial-ics"


def calendar_token(user) -> str:
    return signing.dumps(user.pk, salt=SALT)


def calendar_url(user) -> str:
    from apps.comms.utils import absolute_url
    return absolute_url(f"/manage/calendar/{calendar_token(user)}/editorial.ics")


def _esc(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,")


def editorial_ics(request, token):
    from apps.accounts.models import User

    from .models import ReviewAssignment

    try:
        uid = signing.loads(token, salt=SALT, max_age=180 * 86400)
    except signing.BadSignature:
        raise Http404 from None
    user = User.objects.filter(pk=uid, is_active=True).first()
    if not user or not (user.is_superuser or user.has_editorial_access()):
        raise Http404

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0",
             "PRODID:-//CC Journal//Editorial//EN",
             "X-WR-CALNAME:Editorial deadlines"]
    qs = (ReviewAssignment.objects
          .filter(date_completed__isnull=True, declined=False,
                  date_due__isnull=False)
          .select_related("reviewer", "review_round__submission"))
    for a in qs:
        sub = a.review_round.submission
        d = a.date_due.strftime("%Y%m%d")
        lines += [
            "BEGIN:VEVENT",
            f"UID:review-{a.pk}@ccjournal",
            f"DTSTART;VALUE=DATE:{d}",
            f"SUMMARY:{_esc(f'Review due — #{sub.pk} ({a.reviewer.full_name})')}",
            f"DESCRIPTION:{_esc(f'/manage/reviews/{sub.pk}/')}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    resp = HttpResponse("\r\n".join(lines) + "\r\n",
                        content_type="text/calendar; charset=utf-8")
    resp["Content-Disposition"] = 'inline; filename="editorial.ics"'
    return resp
