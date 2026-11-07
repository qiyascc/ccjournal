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

def notifications(request):
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        return {"unread_notifications": user.notifications.filter(is_read=False).count()}
    return {"unread_notifications": 0}


def webpush(request):
    from django.conf import settings
    return {"webpush_public_key": getattr(settings, "WEBPUSH_PUBLIC_KEY", "")}
